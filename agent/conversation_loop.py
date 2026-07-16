"""
Nexa Agent — Conversation Loop (Enhanced)
=========================================

This module contains the core conversation loop for :class:`NexaAgent`,
now enhanced with:

    - Iteration budget tracking (prevents infinite tool loops).
    - Error classification + adaptive retry.
    - Message sanitization before every LLM call.
    - Context compression when the transcript exceeds the token budget.
    - Memory curation after each turn (the "getting smarter" loop).
    - Learning graph recording (tracks tool success rates).

Separated from ``run_agent.py`` for clarity.
``agent/conversation_loop.py`` pattern.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.context_compressor import ContextCompressor
from agent.error_classifier import classify_error, is_context_overflow
from agent.iteration_budget import IterationBudget
from agent.learning_graph import LearningGraph
from agent.memory_curator import MemoryCurator
from agent.message_sanitizer import sanitize_messages
from nexa.constants import NEXA_NAME
from nexa.provider import LLMProvider
from nexa.state import ConversationDB
from tools.registry import ToolRegistry


async def run_conversation(
    provider: LLMProvider,
    registry: ToolRegistry,
    messages: List[Dict[str, Any]],
    db: Optional[ConversationDB] = None,
    user_input: str = "",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run an iterative tool-calling conversation loop with full hardening.

    Yields events as dicts:

    - ``{"type": "thinking"}`` — loop started.
    - ``{"type": "compressing"}`` — context compression triggered.
    - ``{"type": "token", "text": "..."}`` — a content delta.
    - ``{"type": "tool_call", "name": "...", "arguments": {...}}`` — tool requested.
    - ``{"type": "tool_result", "name": "...", "result": {...}}`` — tool executed.
    - ``{"type": "memory", "memories": [...]}`` — memories curated after turn.
    - ``{"type": "done", "answer": "..."}`` — final answer.
    - ``{"type": "error", "message": "..."}`` — error occurred.

    Args:
        provider:   The :class:`~provider.LLMProvider` to call.
        registry:   The :class:`~tools.registry.ToolRegistry` for tool dispatch.
        messages:   The full transcript (system + history + user input).
        db:         Optional DB for memory curation + learning graph.
        user_input: The original user input (for memory curation).

    Yields:
        Event dicts as described above.
    """
    yield {"type": "thinking"}

    # Initialize hardening subsystems.
    budget = IterationBudget()
    compressor = ContextCompressor(provider=provider)
    learning_graph = LearningGraph(db) if db else None
    curator = MemoryCurator(db) if db else None

    tools = registry.get_openai_schemas()
    tool_results: List[Dict[str, Any]] = []

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
            # Replace the working transcript with the compressed one.
            messages = clean_messages

        accumulated_content: List[str] = []

        # Call the LLM with error classification + retry.
        try:
            async for event_type, payload in provider.chat_stream(
                messages, tools=tools, registry=registry
            ):
                if event_type == "token":
                    accumulated_content.append(payload)
                    yield {"type": "token", "text": payload}
                elif event_type == "tool_call":
                    result_dict = payload.to_dict()
                    tool_results.append(result_dict)
                    # Record outcome in the learning graph.
                    if learning_graph:
                        await learning_graph.record_tool_outcome(
                            result_dict["tool"], result_dict["ok"]
                        )
                    yield {
                        "type": "tool_result",
                        "name": result_dict["tool"],
                        "result": result_dict,
                    }
                elif event_type == "error":
                    # Classify and potentially retry.
                    yield {"type": "error", "message": payload}
                    return
                elif event_type == "done":
                    break
        except Exception as exc:
            classified = classify_error(exc)
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
            # Curate memories from this turn (the "getting smarter" loop).
            if curator and user_input:
                new_memories = await curator.curate_turn(
                    user_input, content, tool_results
                )
                if new_memories:
                    yield {"type": "memory", "memories": new_memories}

            yield {"type": "done", "answer": content or "(no response)"}
            return

    # Iteration budget exhausted.
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
