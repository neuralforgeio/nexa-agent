"""
Nexa Agent — Subagent Delegation Tool
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

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, Dict, Optional

from tools.registry import ToolRegistry


async def delegate(
    task: str,
    context: Optional[str] = None,
    max_iterations: int = 3,
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
                        (default 3, lower than the parent's 8 to prevent
                        runaway subtask execution).

    Returns:
        A summary string of the sub-agent's work, including any tool
        results it produced.

    Raises:
        ValueError: If the task is empty or the provider is not configured.
    """
    if not task or not task.strip():
        raise ValueError("task is required for delegation")

    # Build the sub-agent's system prompt.
    system_prompt = _build_subagent_prompt(task, context, max_iterations)

    # Get the provider from the module-level agent instance.
    # We use a lazy import to avoid circular dependencies.
    try:
        from run_agent import _get_agent
        agent = _get_agent()
    except Exception:
        return "[delegate] Could not access the agent instance."

    provider = agent.provider
    registry: ToolRegistry = agent.registry

    # Build the sub-agent transcript.
    transcript: list[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    tools = registry.get_openai_schemas()
    accumulated_content: list[str] = []
    tool_results: list[str] = []
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        try:
            # Use the provider's streaming method.
            async for event_type, payload in provider.chat_stream(
                transcript, tools=tools, registry=registry
            ):
                if event_type == "token":
                    accumulated_content.append(payload)
                elif event_type == "tool_call":
                    result_dict = payload.to_dict()
                    tool_results.append(
                        f"[{result_dict['tool']}] {'OK' if result_dict['ok'] else 'FAIL'}: "
                        f"{result_dict['output'][:200]}"
                    )
                elif event_type == "error":
                    return f"[delegate error] {payload}"
                elif event_type == "done":
                    break
        except Exception as e:
            return f"[delegate error] {e}"

        # Check if the sub-agent produced a final answer.
        content = "".join(accumulated_content)
        if not _has_pending_tool_calls(transcript):
            break
        accumulated_content.clear()

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
    """
    parts = [
        "You are a Nexa sub-agent. You have been delegated a specific task.",
        f"Complete this task within {max_iterations} tool-call iterations.",
        "Be focused, efficient, and return a clear summary of your work.",
        "",
        f"Task: {task}",
    ]
    if context:
        parts.append(f"Context: {context}")
    return "\n".join(parts)


def _has_pending_tool_calls(messages: list[Dict[str, Any]]) -> bool:
    """
    Check if the last assistant message has unanswered tool calls.

    Args:
        messages: The sub-agent's transcript.

    Returns:
        True if there are pending tool calls awaiting results.
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
            "type": "number",
            "description": "Max tool-call iterations for the sub-agent (default 3).",
        },
    },
    "required": ["task"],
}
