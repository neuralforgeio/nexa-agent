"""
Nexa Agent — Conversation Loop
==============================

This module contains the core conversation loop for :class:`NexaAgent`.
It is separated from ``run_agent.py`` for clarity, mirroring Hermes Agent's
``agent/conversation_loop.py`` pattern.

The loop:
    1. Build the system prompt (identity + tool catalog + memory).
    2. Call the LLM provider (streaming).
    3. If the model requests tool calls, execute them and feed results back.
    4. Repeat until the model produces a final answer or the iteration
       budget is exhausted.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
from typing import Any, AsyncGenerator, Dict, List

from nexa_constants import NEXA_MAX_TOOL_ITERATIONS, NEXA_NAME
from provider import LLMProvider
from tools.registry import ToolRegistry


async def run_conversation(
    provider: LLMProvider,
    registry: ToolRegistry,
    messages: List[Dict[str, Any]],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run an iterative tool-calling conversation loop.

    Yields events as dicts:

    - ``{"type": "thinking"}`` — loop started.
    - ``{"type": "token", "text": "..."}`` — a content delta.
    - ``{"type": "tool_call", "name": "...", "arguments": {...}}`` — tool requested.
    - ``{"type": "tool_result", "name": "...", "result": {...}}`` — tool executed.
    - ``{"type": "done", "answer": "..."}`` — final answer.
    - ``{"type": "error", "message": "..."}`` — error occurred.

    Args:
        provider: The :class:`~provider.LLMProvider` to call.
        registry: The :class:`~tools.registry.ToolRegistry` for tool dispatch.
        messages: The full transcript (system + history + user input).

    Yields:
        Event dicts as described above.
    """
    yield {"type": "thinking"}

    tools = registry.get_openai_schemas()
    iterations = 0

    while iterations < NEXA_MAX_TOOL_ITERATIONS:
        iterations += 1
        accumulated_content: List[str] = []

        try:
            async for event_type, payload in provider.chat_stream(messages, tools=tools, registry=registry):
                if event_type == "token":
                    accumulated_content.append(payload)
                    yield {"type": "token", "text": payload}
                elif event_type == "tool_call":
                    result_dict = payload.to_dict()
                    yield {
                        "type": "tool_result",
                        "name": result_dict["tool"],
                        "result": result_dict,
                    }
                elif event_type == "error":
                    yield {"type": "error", "message": payload}
                    return
                elif event_type == "done":
                    break
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
            return

        # If no tool calls were made, the accumulated content is the answer.
        content = "".join(accumulated_content)
        if not _has_pending_tool_calls(messages):
            yield {"type": "done", "answer": content or "(no response)"}
            return

    # Iteration budget exhausted.
    yield {
        "type": "done",
        "answer": f"[{NEXA_NAME}] reached the tool-call iteration cap ({NEXA_MAX_TOOL_ITERATIONS}).",
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
