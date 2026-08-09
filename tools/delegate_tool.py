"""
OpenForge — Subagent Delegation Tool
=====================================

This module implements the ``delegate`` tool, which allows the main agent
to spawn a sub-agent for handling a specific subtask in isolation. The
sub-agent gets its own conversation context, tool set, and iteration
budget, then returns a summary result to the parent agent.

Use cases:
    - Breaking complex tasks into smaller, focused subtasks.
    - Running independent operations in parallel.
    - Isolating potentially dangerous tool calls.

The sub-agent inherits the parent's provider and tool registry but gets
a fresh transcript with a focused system prompt.

Architecture note:
    The active :class:`~run_agent.OpenForgeAgent` instance is discovered via
    :func:`run_agent.get_active_agent`. The CLI / server / TUI must call
    :func:`run_agent.set_active_agent` at startup for delegation to work.
    If no agent is registered, ``delegate`` returns a clear error message
    rather than raising — this keeps the parent agent's turn alive.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, Dict, List, Optional

from tools.registry import ToolRegistry

#: Minimum / maximum allowed iterations for a sub-agent.
MIN_ITERATIONS: int = 1
MAX_ITERATIONS: int = 8

#: Default iteration budget (lower than the parent's 8 to prevent runaway).
DEFAULT_ITERATIONS: int = 3


async def delegate(
    task: str,
    context: Optional[str] = None,
    max_iterations: int = DEFAULT_ITERATIONS,
    **_: Any,
) -> str:
    """
    Spawn a sub-agent to handle a specific subtask.

    The sub-agent runs with its own conversation loop, tool access, and
    iteration budget. It returns a text summary of its work.

    Args:
        task:           The subtask description for the sub-agent.
        context:        Optional additional context to pass to the sub-agent.
        max_iterations: Maximum tool-call iterations for the sub-agent
                        (default 3, clamped to [1, 8]).

    Returns:
        A summary string of the sub-agent's work, including any tool
        results it produced. On error, returns a string prefixed with
        ``[delegate error]``.

    Raises:
        ValueError: If the task is empty.

    Example:
        >>> result = await delegate(
        ...     task="Read forge/config.py and summarize its purpose",
        ...     max_iterations=2,
        ... )
        >>> "Sub-agent result" in result
        True
    """
    if not task or not task.strip():
        raise ValueError("task is required for delegation")

    # Clamp max_iterations to a safe range.
    max_iterations = max(MIN_ITERATIONS, min(MAX_ITERATIONS, int(max_iterations)))

    # Build the sub-agent's system prompt.
    system_prompt = _build_subagent_prompt(task, context, max_iterations)

    # Discover the active agent instance (set by CLI/server at startup).
    try:
        from src.run_agent import get_active_agent
        agent = get_active_agent()
    except Exception:
        return "[delegate] Could not import src.run_agent.get_active_agent."

    if agent is None:
        return "[delegate] No active agent instance. Call set_active_agent() at startup."

    provider = agent.provider
    registry: ToolRegistry = agent.registry

    # Build the sub-agent transcript (fresh, isolated context).
    transcript: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    tools = registry.get_openai_schemas()
    accumulated_content: List[str] = []
    tool_results: List[str] = []
    iterations = 0

    # v4.1.0: delegate drives the iteration loop itself. Each pass calls
    # chat_stream, which internally recurses via ``_depth`` on tool calls
    # (that's correct behaviour — the recursion is what EXECUTES the tool
    # and fetches the follow-up answer). What we must NOT do is wrap that
    # in an identical outer loop that re-emits the same tokens (v2.x bug).
    # So: one ``chat_stream`` call per iteration, and we stop as soon as no
    # tool calls are pending.
    while iterations < max_iterations:
        iterations += 1
        try:
            async for event_type, payload in provider.chat_stream(
                transcript, tools=tools, registry=registry, _depth=0
            ):
                if event_type == "token":
                    accumulated_content.append(payload)
                elif event_type == "tool_call":
                    result_dict = payload.to_dict()
                    tool_results.append(
                        f"[{result_dict['tool']}] {'OK' if result_dict['ok'] else 'FAIL'}: "
                        f"{str(result_dict.get('output', ''))[:200]}"
                    )
                elif event_type == "error":
                    return f"[delegate error] {payload}"
                elif event_type == "done":
                    break
        except Exception as exc:
            return f"[delegate error] {exc}"

        # If the sub-agent produced a final answer (no pending tool calls), stop.
        if not _has_pending_tool_calls(transcript):
            break

    # Build the summary.
    final_answer = "".join(accumulated_content) or "(sub-agent produced no text)"
    summary_parts = [f"Sub-agent result: {final_answer}"]
    if tool_results:
        summary_parts.append(f"Tools used ({len(tool_results)}):")
        for tr in tool_results:
            summary_parts.append(f"  - {tr}")

    return "\n".join(summary_parts)


def _build_subagent_prompt(
    task: str, context: Optional[str], max_iterations: int
) -> str:
    """
    Build the system prompt for the sub-agent.

    Args:
        task:           The subtask description.
        context:        Optional additional context.
        max_iterations: The iteration budget for this sub-agent.

    Returns:
        A focused system prompt string.

    Example:
        >>> prompt = _build_subagent_prompt("read file", None, 3)
        >>> "read file" in prompt and "3" in prompt
        True
    """
    parts = [
        "You are a Forge sub-agent. You have been delegated a specific task.",
        f"Complete this task within {max_iterations} tool-call iterations.",
        "Be focused, efficient, and return a clear summary of your work.",
        "",
        f"Task: {task}",
    ]
    if context:
        parts.append(f"Context: {context}")
    return "\n".join(parts)


def _has_pending_tool_calls(messages: List[Dict[str, Any]]) -> bool:
    """
    Check if the last assistant message has unanswered tool calls.

    Args:
        messages: The sub-agent's transcript.

    Returns:
        ``True`` if there are tool calls awaiting results, else ``False``.

    Example:
        >>> _has_pending_tool_calls([])
        False
        >>> _has_pending_tool_calls([
        ...     {"role": "assistant", "content": "",
        ...      "tool_calls": [{"id": "x", "function": {"name": "t", "arguments": "{}"}}]},
        ... ])
        True
    """
    if not messages:
        return False
    last = messages[-1]
    if last.get("role") != "assistant" or not last.get("tool_calls"):
        return False
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    return any(tc.get("id") not in answered for tc in last["tool_calls"])


# Schema for OpenAI function-calling.
DELEGATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "The subtask to delegate to the sub-agent.",
        },
        "context": {
            "type": "string",
            "description": "Optional additional context for the sub-agent.",
        },
        "max_iterations": {
            "type": "integer",
            "description": "Max tool-call iterations for the sub-agent (default 3, max 8).",
        },
    },
    "required": ["task"],
}
