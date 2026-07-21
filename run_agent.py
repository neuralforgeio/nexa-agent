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
        resolved_url, resolved_model, resolved_key = resolve_provider(provider_name)
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

    def _build_transcript(
        self, user_input: str, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build the message transcript from system prompt, history, and input.

        Loads long-term memory (MEMORY.md, USER.md) and injects it into the
        system prompt so the agent "remembers" across sessions. Also pulls
        learning-graph stats so the prompt reflects tool success rates.

        Args:
            user_input: The latest user message.
            history:    Prior messages (oldest first).

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
        # Note: get_stats() is async; in this sync context we skip it to avoid
        # blocking. The conversation_loop re-computes stats internally.
        learning_stats = None

        system_prompt = build_system_prompt(
            self.registry,
            memory_digest=memory_digest,
            user_profile=user_profile,
            learning_stats=learning_stats,
        )
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
        transcript = self._build_transcript(user_input, history)

        accumulated: List[str] = []
        # v3.1.0: Ask Question Mode — auto-detect quick-answerable messages.
        from agent.ask_question_mode import should_use_quick_mode, is_quick_mode_enabled
        quick = is_quick_mode_enabled() or should_use_quick_mode(user_input)
        async for event in run_conversation(
            self.provider, self.registry, transcript, db=self.db, user_input=user_input,
            failover_chain=self.failover_chain,
            quick_mode=quick,
        ):
            if event["type"] == "token":
                accumulated.append(event["text"])
            elif event["type"] == "tool_result":
                tr = event["result"]
                await self.db.add_message(conv_id, "tool", tr["output"], tr["tool"])
            yield event

        answer = "".join(accumulated) or "(no response)"
        await self.db.add_message(conv_id, "assistant", answer)


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
