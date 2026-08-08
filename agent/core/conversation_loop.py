"""
Nexa Agent — Conversation Loop (v2.0 Enhanced)
================================================

This module contains the core conversation loop for :class:`NexaAgent`,
now enhanced with:

    - Iteration budget tracking (prevents infinite tool loops).
    - Error classification + adaptive retry.
    - Message sanitization before every LLM call.
    - Context compression when the transcript exceeds the token budget.
    - Memory curation after each turn (the "getting smarter" loop).
    - Learning graph recording (tracks tool success rates).

v2.0 additions:
    - Prompt expansion (terse → structured) before sending to the LLM.
    - Self-healer integration (typed remediation plans on errors).
    - Self-improvement reflection loop (extracts meta-rules per turn).
    - Autonomous web learner (proactively fills knowledge gaps).
    - Provider failover chain (retries on the next provider when one fails).
    - Reasoning chain (structured step-by-step trace).
    - Confidence scoring (post-answer sanity check).
    - Adaptive persona (tone/verbosity tracking).

Separated from ``run_agent.py`` for clarity.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.persona.adaptive_persona import AdaptivePersona, persona_block
from agent.learning.autonomous_learner import (
    LearningBudget,
    should_auto_learn,
    learn_about,
    enrich_with_learned_facts,
)
from agent.reasoning.confidence_scorer import score_answer
from agent.context.context_compressor import ContextCompressor
from agent.context.context_enricher import enrich_context
from agent.error.error_classifier import classify_error, is_context_overflow
from agent.error.error_memory import ErrorMemory
from agent.understanding.intent_classifier import classify_intent, intent_block
from agent.core.iteration_budget import IterationBudget
from agent.memory.knowledge_cache import KnowledgeCache
from agent.learning.learning_graph import LearningGraph
from agent.memory.memory_curator import MemoryCurator
from agent.core.message_sanitizer import sanitize_messages
from agent.understanding.pattern_recognizer import PatternRecognizer
from agent.prompt.prompt_expander import expand_prompt, should_expand
from agent.understanding.proactive_suggester import ProactiveSuggester, suggestion_block
from agent.reasoning.reasoning_chain import ReasoningChain
from agent.error.self_healer import SelfHealer
from agent.learning.self_improvement import SelfImprovementLoop
from nexa.constants import NEXA_NAME
from nexa.provider import LLMProvider
from nexa.provider_failover import (
    FailoverChain,
    build_default_chain,
    is_failover_enabled,
)
from nexa.state import ConversationDB
from tools.registry import ToolRegistry


async def run_conversation(
    provider: LLMProvider,
    registry: ToolRegistry,
    messages: List[Dict[str, Any]],
    db: Optional[ConversationDB] = None,
    user_input: str = "",
    *,
    failover_chain: Optional[FailoverChain] = None,
    knowledge_cache: Optional[KnowledgeCache] = None,
    learning_budget: Optional[LearningBudget] = None,
    healer: Optional[SelfHealer] = None,
    improvement_loop: Optional[SelfImprovementLoop] = None,
    persona_adapter: Optional[AdaptivePersona] = None,
    pattern_recognizer: Optional[PatternRecognizer] = None,
    suggester: Optional[ProactiveSuggester] = None,
    web_search_fn=None,
    quick_mode: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run an iterative tool-calling conversation loop with full v2.0 hardening.

    Yields events as dicts:

    - ``{"type": "thinking"}`` — loop started.
    - ``{"type": "expand", "expanded": "..."}`` — prompt was expanded (v2.0).
    - ``{"type": "intent", "intent": {...}}`` — detected intent (v2.0).
    - ``{"type": "autolearn", "query": "...", "fact": {...}}``,
      — autonomous learning fired (v2.0).
    - ``{"type": "compressing", "detail": "..."}`` — context compression.
    - ``{"type": "token", "text": "..."}`` — a content delta.
    - ``{"type": "tool_call", ...}`` — tool requested.
    - ``{"type": "tool_result", "name": "...", "result": {...}}``.
    - ``{"type": "memory", "memories": [...]}`` — memories curated.
    - ``{"type": "failover", "from": "...", "to": "...", "reason": "..."}``
      — provider failover fired (v2.0).
    - ``{"type": "heal", "plan": {...}}`` — healer produced a plan (v2.0).
    - ``{"type": "confidence", "score": ..., "should_enrich": bool}`` (v2.0).
    - ``{"type": "reflection", "summary": "..."}`` (v2.0).
    - ``{"type": "suggestions", "items": [...]}`` (v2.0).
    - ``{"type": "done", "answer": "..."}`` — final answer.
    - ``{"type": "error", "message": "..."}`` — error occurred.

    Args:
        provider:          The :class:`~nexa.provider.LLMProvider` to call.
        registry:          The :class:`~tools.registry.ToolRegistry`.
        messages:          The full transcript (system + history + user input).
        db:                Optional DB for memory curation + learning graph.
        user_input:        The original user input (for memory curation).
        failover_chain:    Optional :class:`FailoverChain` for v2.0 failover.
        knowledge_cache:   Optional :class:`KnowledgeCache` for v2.0 enrichment.
        learning_budget:   Optional :class:`LearningBudget` for autolearn.
        healer:            Optional :class:`SelfHealer` for v2.0 healing.
        improvement_loop:  Optional :class:`SelfImprovementLoop`.
        persona_adapter:   Optional :class:`AdaptivePersona`.
        pattern_recognizer:Optional :class:`PatternRecognizer`.
        suggester:         Optional :class:`ProactiveSuggester`.
        web_search_fn:     Optional async callable for autonomous learning.

    Yields:
        Event dicts as described above.
    """
    yield {"type": "thinking"}

    # Initialize hardening subsystems.
    budget = IterationBudget()
    compressor = ContextCompressor(provider=provider)
    learning_graph = LearningGraph(db) if db else None
    curator = MemoryCurator(db) if db else None

    # v2.0 subsystems (lazily created if not provided).
    healer = healer or SelfHealer()
    improvement_loop = improvement_loop or SelfImprovementLoop()
    persona_adapter = persona_adapter or AdaptivePersona()
    pattern_recognizer = pattern_recognizer or PatternRecognizer()
    suggester = suggester or ProactiveSuggester()
    error_memory = ErrorMemory()
    reasoning = ReasoningChain()

    # Observe the user message for persona + patterns.
    if user_input:
        persona_adapter.observe(user_input)
        pattern_recognizer.observe(user_input)

    # v2.0: prompt expansion (terse → structured).
    if user_input and should_expand(user_input):
        history = [m for m in messages if m.get("role") in ("user", "assistant")]
        expanded = expand_prompt(user_input, history)
        yield {"type": "expand", "expanded": expanded.expanded[:200] + "…"}
        # v4.15.1 fix: llama.cpp --jinja templates REQUIRE all system messages
        # to be at index 0. Injecting a mid-conversation "system" role breaks
        # them. Fold the expansion into the EXISTING system message at index 0.
        if messages and messages[0].get("role") == "system":
            messages[0] = dict(messages[0])
            messages[0]["content"] = (
                messages[0]["content"]
                + "\n\n[Expanded intent — terse input expanded]\n"
                + expanded.expanded.strip()
            )
        else:
            # Fallback: attach as an assistant note right before the user msg.
            messages.insert(
                len(messages) - 1,
                {"role": "assistant", "content": "[Expanded intent] " + expanded.expanded.strip()},
            )

    # v2.0: intent detection.
    if user_input:
        intent = classify_intent(user_input)
        yield {"type": "intent", "intent": intent.to_dict()}
        reasoning.think(
            f"User intent detected as '{intent.label}'"
            + (f" ({intent.sub_type})" if intent.sub_type else "")
        )

    # v2.0: autonomous learning (if enabled and budget remains).
    if learning_budget and web_search_fn and user_input:
        known = set()  # In production: pull from knowledge_cache.list_all()
        query = should_auto_learn(user_input, learning_budget, known)
        if query:
            yield {"type": "autolearn", "query": query}
            fact = await learn_about(
                query, learning_budget, web_search_fn, knowledge_cache
            )
            if fact:
                yield {"type": "autolearn", "query": query, "fact": fact.to_dict()}
                reasoning.act(
                    thought=f"Autonomously learned about '{query}'",
                    action=f"web_search: {query}",
                    observation=fact.summary[:200],
                    confidence=fact.confidence,
                )

    # v4.1.0: Ask Question Mode — when True, skip tools (instant response).
    tools = None if quick_mode else registry.get_openai_schemas()
    tool_results: List[Dict[str, Any]] = []
    errors_seen: List[str] = []

    while not budget.exhausted:
        budget.consume("llm_call")

        # Sanitize messages before sending.
        clean_messages = sanitize_messages(messages)

        # Compress if over budget.
        clean_messages, was_compressed = await compressor.compress_if_needed(
            clean_messages
        )
        if was_compressed:
            yield {"type": "compressing", "detail": "context compressed to fit token budget"}
            messages = clean_messages
            reasoning.think("Context was compressed to fit the token budget.")

        accumulated_content: List[str] = []

        # Call the LLM with error classification + retry + v2.0 failover.
        try:
            async for event_type, payload in provider.chat_stream(
                messages, tools=tools, registry=registry
            ):
                if event_type == "token":
                    accumulated_content.append(payload)
                    yield {"type": "token", "text": payload}
                elif event_type == "reasoning":
                    # Surface the model's chain-of-thought for the UI's
                    # Thought Process panel.
                    yield {"type": "thinking", "text": payload}
                elif event_type == "tool_call":
                    result_dict = payload.to_dict()
                    tool_results.append(result_dict)
                    if learning_graph:
                        await learning_graph.record_tool_outcome(
                            result_dict["tool"], result_dict["ok"]
                        )
                    reasoning.act(
                        thought=f"Called tool '{result_dict['tool']}'",
                        action=result_dict["tool"],
                        observation=str(result_dict.get("output", ""))[:200],
                        confidence=1.0 if result_dict["ok"] else 0.3,
                    )
                    yield {
                        "type": "tool_result",
                        "name": result_dict["tool"],
                        "result": result_dict,
                    }
                elif event_type == "error":
                    # v2.0: healer produces a plan.
                    plan = healer.plan(payload, context={"tool_name": "unknown"})
                    error_memory.record(payload, plan.category, plan.remediation)
                    errors_seen.append(payload)
                    yield {"type": "heal", "plan": plan.to_dict()}
                    if plan.escalate:
                        yield {"type": "error", "message": payload}
                        return
                    # If plan says retry, the outer try/except will handle backoff.
                    yield {"type": "error", "message": payload}
                    return
                elif event_type == "done":
                    break
        except Exception as exc:
            classified = classify_error(exc)
            # v2.0: healer plan for the exception.
            plan = healer.plan(exc)
            error_memory.record(str(exc), plan.category, plan.remediation)
            errors_seen.append(str(exc))
            yield {"type": "heal", "plan": plan.to_dict()}

            # v4.1.0: provider failover (if enabled and chain provided).
            if (
                failover_chain is not None
                and is_failover_enabled()
                and not plan.escalate
            ):
                next_provider = failover_chain.advance(reason=str(exc))
                if next_provider is not None:
                    # v4.1.0: ACTUALLY swap the provider's connection params
                    # so the next iteration hits the new provider, not the
                    # dead one. This was a dead-code scaffold in v2.0.
                    provider.base_url = next_provider.base_url
                    provider.api_key = next_provider.api_key
                    provider.model = next_provider.model
                    provider._client = None  # force AsyncOpenAI re-init
                    yield {
                        "type": "failover",
                        "from": (
                            failover_chain.tracker.all_providers()[0].name
                            if failover_chain.tracker.all_providers()
                            else "primary"
                        ),
                        "to": next_provider.name,
                        "reason": str(exc),
                    }
                    # Small backoff before retrying on the new provider.
                    await asyncio.sleep(min(2.0, classified.delay_ms / 1000))
                    continue

            if classified.should_retry and not budget.exhausted:
                yield {
                    "type": "compressing",
                    "detail": f"retrying after {classified.reason} ({classified.delay_ms}ms)",
                }
                await asyncio.sleep(classified.delay_ms / 1000)
                continue
            else:
                yield {"type": "error", "message": classified.reason}
                return

        # If no tool calls were made, the accumulated content is the answer.
        content = "".join(accumulated_content)
        if not _has_pending_tool_calls(messages):
            # v2.0: confidence scoring.
            report = score_answer(
                content,
                question=user_input,
                tool_calls=[
                    {"name": r["tool"], "ok": r["ok"]} for r in tool_results
                ],
            )
            yield {
                "type": "confidence",
                "score": report.score,
                "should_enrich": report.should_enrich,
                "reasons": report.reasons,
            }
            reasoning.think(
                f"Confidence in final answer: {report.score:.2f}"
                + (" (low — consider enrichment)" if report.should_enrich else "")
            )

            # Curate memories from this turn.
            if curator and user_input:
                new_memories = await curator.curate_turn(
                    user_input, content, tool_results
                )
                if new_memories:
                    yield {"type": "memory", "memories": new_memories}

            # v4.1.0: teach the proactive suggester + pattern recognizer
            # from this turn's tool activity (instead of leaving them
            # dormant like they were in v2.0).
            try:
                _action = (
                    "ran_tests"
                    if any(
                        tr.get("tool") == "run_terminal_command"
                        and tok in (tr.get("output", "") or "").lower()
                        for tr in tool_results
                        for tok in ("pytest", "npm test", "test session", "collected")
                    )
                    else (
                        "used_tools"
                        if tool_results
                        else "answered_directly"
                    )
                )
                suggester.observe(
                    action=_action,
                    tools_used=[r.get("tool", "") for r in tool_results],
                    had_error=bool(errors_seen) or any(
                        not r.get("ok", True) for r in tool_results
                    ),
                )
            except Exception:
                pass

            # v4.1.0: periodic pattern-recognition summary. Every 3 turns
            # with tools/fire we surface what the recognizer learned about
            # the user's working style as a ``patterns`` SSE event.
            try:
                if budget.used % 3 == 0 and tool_results:
                    rep = pattern_recognizer.report()
                    block = rep.render() if hasattr(rep, "render") else str(rep)
                    if block and block.strip():
                        yield {"type": "patterns", "detail": block}
            except Exception:
                pass

            # v2.0: self-improvement reflection.
            reflection = improvement_loop.reflect_on_turn(
                user_message=user_input,
                assistant_answer=content,
                tool_calls=[
                    {"name": r["tool"], "ok": r["ok"]} for r in tool_results
                ],
                errors=errors_seen,
                turn_id=budget.used,
            )
            yield {"type": "reflection", "summary": reflection.summary}

            # v2.0: proactive suggestions.
            suggestions = suggester.suggest(max_items=3)
            if suggestions:
                yield {
                    "type": "suggestions",
                    "items": [s.to_dict() for s in suggestions],
                }

            # v4.1.0: persist error memory to ~/.nexa/memory/errors.json
            # so error records survive process restarts.
            try:
                error_memory.save()
            except Exception:
                # Persistence failure must not break the loop.
                pass

            # v4.1.0: record trajectory (prompt → tool → response) for fine-tuning.
            try:
                from agent.observability.trajectory_recorder import (
                    TrajectoryRecorder,
                    TurnTrajectory,
                    is_trajectory_enabled,
                )
                if is_trajectory_enabled():
                    rec = TrajectoryRecorder()
                    rec.record(TurnTrajectory(
                        session_id=getattr(db, "_current_conv_id", "unknown") if db else "unknown",
                        turn_id=budget.used,
                        user_message=user_input,
                        system_prompt=messages[0].get("content", "") if messages else "",
                        tool_calls=[
                            {"name": r["tool"], "ok": r["ok"], "output": str(r.get("output", ""))[:500]}
                            for r in tool_results
                        ],
                        assistant_response=content or "",
                        errors=errors_seen,
                        # v4.1.6: use a proper locals() check instead of dir().
                        confidence=report.score if "report" in locals() else 0.5,
                    ))
            except Exception:
                pass

            yield {"type": "done", "answer": content or "(no response)"}
            return

    # Iteration budget exhausted.
    # v4.1.0: persist error memory before final yield.
    try:
        error_memory.save()
    except Exception:
        pass
    yield {
        "type": "done",
        "answer": f"[{NEXA_NAME}] reached the tool-call iteration cap "
        f"({budget.max_iterations}). {budget.summary()}",
    }


def _has_pending_tool_calls(messages: List[Dict[str, Any]]) -> bool:
    """
    Check if the last assistant message has tool calls awaiting results.

    Args:
        messages: The current transcript.

    Returns:
        ``True`` if the last assistant message has ``tool_calls`` that
        haven't been answered by a ``tool`` role message yet.
    """
    if not messages:
        return False
    last = messages[-1]
    if last.get("role") != "assistant" or not last.get("tool_calls"):
        return False
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    return any(tc.get("id") not in answered for tc in last["tool_calls"])
