"""
Nexa Agent — Agent Runner
=========================

This module defines :class:`NexaAgent`, the main agent class that ties
together the LLM provider, tool registry, and storage layer. It also
provides a ``main()`` entry point for running the agent standalone.

Usage as a library::

    from run_agent import NexaAgent
    agent = NexaAgent(provider_name="ollama", model="llama3.2")
    async for event in agent.run_streaming("Hello", conv_id="..."):
        print(event)

Usage as a CLI::

    python run_agent.py --provider ollama --model llama3.2 "Hello, Nexa!"

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import asyncio
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.conversation_loop import run_conversation
from agent.prompt_builder import build_system_prompt
from nexa.constants import NEXA_MAX_CONTEXT_MESSAGES, NEXA_NAME
from nexa.provider import LLMProvider
from providers.catalog import resolve_provider
from nexa.state import ConversationDB
from tools.registry import ToolRegistry, create_default_registry


# ---------------------------------------------------------------------------
# Module-level active-agent singleton
# ---------------------------------------------------------------------------
# Used by tools that need to access the running agent instance (e.g. the
# ``delegate`` tool spawns a sub-agent via the same provider/registry).
# This avoids passing the agent through every tool call (which would break
# the tool registry's flat ``**kwargs`` interface) while still allowing
# tools to discover the active agent at runtime.
_agent_singleton: Optional["NexaAgent"] = None


def set_active_agent(agent: "NexaAgent") -> None:
    """
    Register the currently-active agent instance.

    Called by the CLI / server / TUI at startup so that tools like
    ``delegate`` can discover the agent at runtime.

    Args:
        agent: The :class:`NexaAgent` instance to register.
    """
    global _agent_singleton
    _agent_singleton = agent


def get_active_agent() -> Optional["NexaAgent"]:
    """
    Return the currently-active agent instance, or ``None`` if none set.

    Returns:
        The registered :class:`NexaAgent`, or ``None``.
    """
    return _agent_singleton


class NexaAgent:
    """
    The core Nexa Agent — orchestrates LLM calls, tool execution, and storage.

    Attributes:
        provider: The :class:`~provider.LLMProvider` instance.
        registry: The :class:`~tools.registry.ToolRegistry` with all tools.
        db:       The :class:`~storage.ConversationDB` for persistence.
    """

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        registry: Optional[ToolRegistry] = None,
        db: Optional[ConversationDB] = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            provider_name: Provider name from the catalog (e.g. ``"ollama"``).
            model:         Override the model identifier.
            api_key:       Override the API key.
            base_url:      Override the base URL.
            registry:      Override the default tool registry.
            db:            Override the default storage instance.
        """
        # Resolve provider config.
        # v3.1.0: first try the ProviderRegistry (custom providers like 'ornith'),
        # then fall back to the catalog (openai, ollama, etc.).
        if provider_name:
            from nexa.provider_registry import ProviderRegistry
            reg = ProviderRegistry()
            custom = reg.get(provider_name)
            if custom is not None:
                # Custom provider found — use its config directly.
                resolved_url = custom.base_url
                resolved_model = custom.model
                resolved_key = custom.api_key or "dummy"
            else:
                # Fall back to catalog/env resolution.
                resolved_url, resolved_model, resolved_key = resolve_provider(provider_name)
        else:
            resolved_url, resolved_model, resolved_key = resolve_provider(None)
        self.provider = LLMProvider(
            api_key=api_key or resolved_key,
            base_url=base_url or resolved_url,
            model=model or resolved_model,
        )
        self.registry = registry or create_default_registry()
        self.db = db or ConversationDB()

        # v3.0.0: build a failover chain if NEXA_FAILOVER_ENABLED=1.
        # The chain lets the conversation loop swap providers on failure.
        self.failover_chain = None
        try:
            from nexa.provider_failover import (
                build_default_chain,
                is_failover_enabled,
            )
            if is_failover_enabled():
                self.failover_chain = build_default_chain(
                    primary_name=provider_name,
                )
        except Exception:
            # Failover is optional; never break init.
            self.failover_chain = None

        # v4.1.0 — v2.0 intelligence mesh: create ONCE and keep as stateful
        # attributes so they accumulate observations across turns instead of
        # being rebuilt (and therefore forgotten) every single turn.
        try:
            from agent.adaptive_persona import AdaptivePersona
            from agent.error_memory import ErrorMemory
            from agent.knowledge_cache import KnowledgeCache
            from agent.orchestrator import Orchestrator
            from agent.pattern_recognizer import PatternRecognizer
            from agent.persona_manager import PersonaManager
            from agent.proactive_suggester import ProactiveSuggester
            from agent.self_healer import SelfHealer
            from agent.self_improvement import SelfImprovementLoop

            self.persona_adapter = AdaptivePersona()
            self.improvement_loop = SelfImprovementLoop()
            self.pattern_recognizer = PatternRecognizer()
            self.suggester = ProactiveSuggester()
            self.knowledge_cache = KnowledgeCache()
            self.healer = SelfHealer()
            self.error_memory = ErrorMemory()
            # Virtual multi-agent (sequential): orchestrator + persona mgr.
            # fresh=True ensures each new NexaAgent starts at PLANNING (not
            # wherever the previous session left off on disk).
            self.orchestrator = Orchestrator(fresh=True)
            self.persona_manager = PersonaManager(self.orchestrator)
        except Exception:
            # The v2.0 modules are optional — never break agent init.
            self.persona_adapter = None
            self.improvement_loop = None
            self.pattern_recognizer = None
            self.suggester = None
            self.knowledge_cache = None
            self.healer = None
            self.error_memory = None
            self.orchestrator = None
            self.persona_manager = None

    def _build_transcript(
        self,
        user_input: str,
        history: List[Dict[str, Any]],
        *,
        quick: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Build the message transcript from system prompt, history, and input.

        Loads long-term memory (MEMORY.md, USER.md) and injects it into the
        system prompt so the agent "remembers" across sessions. Pulls the
        v2.0 intelligence mesh (persona / intent / reasoning / improvement /
        enriched-context) into the prompt, and — when ``quick`` is True —
        strips the tool catalog to save tokens (v4.1.0).

        Args:
            user_input: The latest user message.
            history:    Prior messages (oldest first).
            quick:      Quick-mode — strip the "Available Tools" section.

        Returns:
            The full transcript ready for the LLM API call.
        """
        # v3.0.0: load long-term memory + user profile from ~/.nexa/memory/.
        memory_digest = ""
        user_profile = ""
        learning_stats = None
        try:
            from agent.memory_files import (
                build_memory_file_digest,
                read_user_file,
            )
            memory_digest = build_memory_file_digest()
            user_profile = read_user_file() or ""
        except Exception:
            # Memory subsystem must never break the agent loop.
            pass

        # Load learning-graph stats (tool success rates) — best-effort.
        learning_stats = None

        # --------------------------------------------------------------
        # v4.1.0: populate the intelligence-mesh prompt sections that were
        # previously defined-but-never-passed (AdaptivePersona, Intent,
        # SelfImprovement, ContextEnricher, ReasoningChain).
        # --------------------------------------------------------------
        persona_block_text = ""
        intent_block_text = ""
        improvement_digest = ""
        enriched_context = ""
        reasoning_block_text = ""
        virtual_agent_block = ""
        try:
            from agent.adaptive_persona import persona_block
            from agent.context_enricher import enrich_context
            from agent.intent_classifier import classify_intent, intent_block
            from agent.persona_manager import base_persona_block
            from agent.reasoning_chain import ReasoningChain

            if self.persona_adapter is not None:
                persona_block_text = persona_block(self.persona_adapter.persona())
            if user_input:
                intent_block_text = intent_block(classify_intent(user_input))
            if self.improvement_loop is not None:
                improvement_digest = self.improvement_loop.build_improvement_digest()

            # enrich_context returns an EnrichedContext object; pull its
            # rendered block (the string section the prompt actually needs).
            if self.knowledge_cache is not None:
                _ectx = enrich_context(
                    user_message=user_input or "",
                    user_profile=user_profile or None,
                    long_term_memory=memory_digest or None,
                    knowledge_cache=self.knowledge_cache,
                    recent_tool_results=None,
                )
                enriched_context = getattr(_ectx, "block", None) or (
                    _ectx.render() if hasattr(_ectx, "render") else ""
                )

            # Reasoning-so-far (last 8 steps, if any were recorded this turn).
            # The ReasoningChain instance is per-turn, so on a fresh turn this
            # is empty; we pass it anyway so the section slot exists.
            _reasoner = ReasoningChain()
            reasoning_block_text = _reasoner.render()

            # Virtual multi-agent: prepend the active persona's identity block
            # (Planner / Explorer / Coder / Reviewer / Final Reporter) so the
            # model knows which hat it is wearing right now. Only when the
            # user has enabled the protocol — otherwise the agent answers
            # normally without wearing a persona.
            import os as _os
            if self.orchestrator is not None and _os.environ.get(
                "NEXA_ORCHESTRATOR", "0"
            ).lower() in ("1", "true", "yes"):
                virtual_agent_block = base_persona_block(self.orchestrator.current_phase)
        except Exception:
            # Intelligence mesh must never break the transcript build.
            pass

        system_prompt = build_system_prompt(
            self.registry,
            memory_digest=memory_digest,
            user_profile=user_profile,
            learning_stats=learning_stats,
            enriched_context=enriched_context,
            improvement_digest=improvement_digest,
            persona_block_text=persona_block_text,
            intent_block_text=intent_block_text,
            reasoning_block_text=reasoning_block_text,
        )

        # Prepend the virtual-agent identity block (v4.1.0).
        if virtual_agent_block:
            system_prompt = virtual_agent_block + "\n\n" + system_prompt

        # v4.1.0: quick mode strips the (large) "Available Tools" section so
        # we don't waste ~2K tokens on a prompt whose model won't be allowed
        # to call tools anyway.
        if quick:
            try:
                from agent.ask_question_mode import build_quick_system_prompt
                system_prompt = build_quick_system_prompt(system_prompt)
            except Exception:
                pass

        transcript: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in history[-NEXA_MAX_CONTEXT_MESSAGES:]:
            if msg.get("role") == "system":
                continue
            transcript.append({"role": msg["role"], "content": msg["content"]})
        transcript.append({"role": "user", "content": user_input})
        return transcript

    async def run_streaming(
        self,
        user_input: str,
        conv_id: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run a streaming conversation turn.

        Yields event dicts with a ``type`` key (see
        :func:`agent.conversation_loop.run_conversation`).

        Args:
            user_input: The user's message text.
            conv_id:    The conversation ID (for persistence).
            history:    Prior messages from storage (optional).

        Yields:
            Event dicts.
        """
        await self.db.init()
        await self.db.add_message(conv_id, "user", user_input)

        history = history or []

        # v3.1.0: Ask Question Mode — decide BEFORE the transcript build so
        # the (large) "Available Tools" section can be stripped (v4.1.0).
        from agent.ask_question_mode import (
            should_use_quick_mode,
            is_quick_mode_enabled,
        )
        quick = is_quick_mode_enabled() or should_use_quick_mode(user_input)

        # Build the system prompt + transcript (personas, memory, and quick
        # prompt-strip all handled inside).
        transcript = self._build_transcript(user_input, history, quick=quick)

        accumulated: List[str] = []
        turn_tool_results: List[Dict[str, Any]] = []
        errors_seen: List[str] = []
        async for event in run_conversation(
            self.provider, self.registry, transcript, db=self.db, user_input=user_input,
            failover_chain=self.failover_chain,
            knowledge_cache=self.knowledge_cache,
            healer=self.healer,
            improvement_loop=self.improvement_loop,
            persona_adapter=self.persona_adapter,
            pattern_recognizer=self.pattern_recognizer,
            suggester=self.suggester,
            quick_mode=quick,
        ):
            if event["type"] == "token":
                accumulated.append(event["text"])
            elif event["type"] == "tool_result":
                tr = event["result"]
                turn_tool_results.append(tr)
                if not tr.get("ok"):
                    errors_seen.append(str(tr.get("output", "")))
                await self.db.add_message(conv_id, "tool", tr["output"], tr["tool"])
            elif event["type"] == "error":
                errors_seen.append(str(event.get("message", "")))
            elif event["type"] == "heal":
                errors_seen.append(str(event.get("plan", "")))
            yield event

        answer = "".join(accumulated) or "(no response)"
        await self.db.add_message(conv_id, "assistant", answer)

        # v4.1.0: advance the virtual multi-agent FSM based on what the
        # turn actually accomplished (plan written / code written / errors
        # seen). The UI's agent badge reads this state on the next turn.
        try:
            self._advance_orchestrator(user_input, answer, turn_tool_results, errors_seen)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _advance_orchestrator(
        self,
        user_input: str,
        answer: str,
        tool_results: List[Dict[str, Any]],
        errors: List[str],
    ) -> None:
        """
        Move the virtual-agent FSM forward after a completed turn.

        Heuristic (deliberately simple — local LLMs emit loosely formatted
        markers): look at the current phase, the tools used this turn, and
        whether any errors surfaced, then invoke ``Orchestrator.decide_next``
        with a matching phase_result.

        Args:
            user_input:   The user's original message.
            answer:       The assistant's final answer.
            tool_results: Tool calls the agent made this turn.
            errors:       Errors seen during the turn (tool/healer events).
        """
        if self.orchestrator is None:
            return
        import os

        # Gate the FSM: only drive phase transitions when the user has
        # activated the multi-agent protocol (NEXA_ORCHESTRATOR=1). Without
        # this env flag the orchestrator stays parked at PLANNING forever,
        # preserving v4.0-compatible single-agent behavior for casual chat.
        if os.environ.get("NEXA_ORCHESTRATOR", "0").lower() not in ("1", "true", "yes"):
            return

        from agent.orchestrator import AgentPhase

        phase = self.orchestrator.current_phase
        tools_used = {tr.get("tool") for tr in tool_results}
        wrote_code = bool(tools_used & {"write_file", "file_patch"})
        saw_error = bool(errors) or any(not tr.get("ok") for tr in tool_results)
        is_complex_request = len(user_input.split()) > 4 or wrote_code

        if phase == AgentPhase.PLANNING and is_complex_request:
            self.orchestrator.decide_next(
                {"needs_research": ("explore" in user_input.lower() or "research" in user_input.lower())}
            )
        elif phase == AgentPhase.EXPLORING:
            self.orchestrator.decide_next({})
        elif phase == AgentPhase.CODING:
            if wrote_code:  # only advance when code actually landed
                self.orchestrator.decide_next({})
        elif phase == AgentPhase.REVIEWING:
            self.orchestrator.decide_next(
                {"saw_error": saw_error, "error_summary": (errors[-1] if errors else "")[:200]}
            )


async def _run_single_turn(agent: NexaAgent, message: str) -> None:
    """
    Run a single non-interactive turn and print events to stdout.

    Args:
        agent:  The :class:`NexaAgent` instance.
        message: The user message.
    """
    await agent.db.init()
    conv = await agent.db.create_conversation(title=message[:48])
    async for event in agent.run_streaming(message, conv["id"]):
        if event["type"] == "token":
            print(event["text"], end="", flush=True)
        elif event["type"] == "tool_result":
            print(f"\n[tool: {event['name']}] {event['result']['output'][:200]}")
        elif event["type"] == "done":
            print(f"\n[{NEXA_NAME}] done.")
        elif event["type"] == "error":
            print(f"\n[error] {event['message']}", file=sys.stderr)


def main() -> None:
    """
    CLI entry point for ``python run_agent.py``.

    Examples::

        python run_agent.py --provider openai "Hello"
        python run_agent.py --provider ollama --model llama3.2 "Hello"
        python run_agent.py --provider llamacpp "Hello"
    """
    parser = argparse.ArgumentParser(
        description=f"{NEXA_NAME} — standalone agent runner",
    )
    parser.add_argument("message", nargs="?", help="The message to send")
    parser.add_argument("--provider", default=None, help="Provider name (ollama, openai, llamacpp, ...)")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--base-url", default=None, help="Custom base URL")
    parser.add_argument("--api-key", default=None, help="API key override")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        sys.exit(1)

    agent = NexaAgent(
        provider_name=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )
    asyncio.run(_run_single_turn(agent, args.message))


if __name__ == "__main__":
    main()
