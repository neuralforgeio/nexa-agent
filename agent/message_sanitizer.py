"""
Nexa Agent — Message Sanitizer
=============================

Cleans and repairs message transcripts before sending them to the LLM.
Inspired by Hermes Agent's ``message_sanitization`` module — original
implementation.

Operations:
    - Strip surrogate code points (U+D800–U+DFFF) that break JSON.
    - Repair malformed tool-call arguments (missing colons, trailing commas).
    - Remove null bytes and other control characters.
    - Ensure all messages have required fields (role, content).
    - Truncate excessively long messages to a safe limit.
    - Close interrupted tool-call sequences (assistant message with
      tool_calls but no corresponding tool result).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
import re
from typing import Any, Dict, List

#: Maximum content length per message (chars) before truncation.
MAX_MESSAGE_CHARS = 50_000

#: Pattern matching surrogate code points (invalid in JSON).
_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")

#: Pattern matching null bytes and other C0 control chars (except tab/newline).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitize a list of messages before sending to the LLM API.

    This function returns a *new* list; the input is not mutated.

    Args:
        messages: The raw message transcript.

    Returns:
        A cleaned copy of the messages list.

    Example::

        clean = sanitize_messages(raw_transcript)
        await provider.chat_completion(messages=clean, ...)
    """
    cleaned: List[Dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Ensure content is a string.
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)

        # Strip surrogates and control characters.
        content = _SURROGATE_RE.sub("\ufffd", content)
        content = _CONTROL_RE.sub("", content)

        # Truncate excessively long content.
        if len(content) > MAX_MESSAGE_CHARS:
            content = content[:MAX_MESSAGE_CHARS] + "\n…[truncated by sanitizer]"

        entry: Dict[str, Any] = {"role": role, "content": content}

        # Preserve tool_call_id for tool-role messages.
        if msg.get("tool_call_id"):
            entry["tool_call_id"] = msg["tool_call_id"]

        # Sanitize tool_calls on assistant messages.
        if msg.get("tool_calls"):
            entry["tool_calls"] = _sanitize_tool_calls(msg["tool_calls"])

        # Preserve name field if present.
        if msg.get("name"):
            entry["name"] = msg["name"]

        cleaned.append(entry)

    # Close any interrupted tool-call sequences.
    cleaned = _close_interrupted_tool_calls(cleaned)

    return cleaned


def _sanitize_tool_calls(tool_calls: List[Any]) -> List[Dict[str, Any]]:
    """
    Repair and clean a list of tool_call objects from an assistant message.

    Args:
        tool_calls: Raw tool_call list (may be malformed).

    Returns:
        A clean list of tool_call dicts with valid JSON arguments.
    """
    sanitized: List[Dict[str, Any]] = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue

        tc_id = tc.get("id", f"call_{len(sanitized)}")
        fn = tc.get("function", {})
        if not isinstance(fn, dict):
            fn = {}

        name = fn.get("name", "")
        if not name:
            continue

        args_str = fn.get("arguments", "{}")
        # Attempt to repair malformed JSON arguments.
        args_str = _repair_json(args_str)

        sanitized.append(
            {
                "id": tc_id,
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            }
        )
    return sanitized


def _repair_json(raw: str) -> str:
    """
    Attempt to repair common JSON malformations in tool-call arguments.

    Fixes:
        - Missing colons between keys and values (``"key" {`` → ``"key": {``).
        - Trailing commas before closing braces/brackets.
        - Unescaped newlines inside strings.

    If repair fails, returns ``"{}"`` (empty args) as a safe fallback.

    Args:
        raw: The raw JSON string.

    Returns:
        A valid JSON string.
    """
    if not raw:
        return "{}"

    # First, try parsing as-is.
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        pass

    # Apply repairs.
    repaired = raw
    # Fix missing colons: "key" { → "key": {
    repaired = re.sub(r'"(\w+)"\s*(?=["{\[\d\-])', r'"\1": ', repaired)
    # Remove trailing commas.
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    # Escape literal newlines inside strings (rough heuristic).
    repaired = repaired.replace("\n", "\\n")

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        # Last resort: return empty args.
        return "{}"


def _close_interrupted_tool_calls(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure every assistant tool_call has a matching tool-role response.

    If the last message is an assistant message with tool_calls but no
    corresponding tool results follow, we append a synthetic tool message
    with an error so the API doesn't reject the request.

    Args:
        messages: The cleaned message list.

    Returns:
        The message list with any interrupted sequences closed.
    """
    if not messages:
        return messages

    last = messages[-1]
    if last.get("role") != "assistant" or not last.get("tool_calls"):
        return messages

    # The last message has tool_calls — check if all are answered.
    answered_ids = {
        m.get("tool_call_id") for m in messages if m.get("role") == "tool"
    }
    unanswered = [
        tc for tc in last["tool_calls"] if tc.get("id") not in answered_ids
    ]

    if not unanswered:
        return messages

    # Append synthetic tool results for unanswered calls.
    for tc in unanswered:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id", "unknown"),
                "content": "[sanitizer] This tool call was interrupted. "
                "Please continue without relying on its result.",
            }
        )

    return messages


def estimate_tokens(text: str) -> int:
    """
    Estimate the token count of a string.

    Uses the heuristic that ~4 characters ≈ 1 token for English text.
    This is approximate; for exact counts use a tokenizer library.

    Args:
        text: The input string.

    Returns:
        Estimated token count.
    """
    return max(1, len(text) // 4)
