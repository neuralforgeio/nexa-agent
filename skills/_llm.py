"""
OpenForge — LLM helper for skills (v4.4.0)
===========================================

A tiny, provider-agnostic adapter so skill handlers can ask the model for a
plain completion without caring which provider object they were handed:
anything exposing ``chat_stream(messages, ...) -> AsyncGenerator[(event,
payload), None]`` works — the real :class:`nexa.provider.LLMProvider` against
llama.cpp in production, or a scripted fake in unit tests.

Keeping this in one place means the streaming/drain logic is written and
tested once, not copied into 40 handlers.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = ["chat", "chat_text", "chat_json"]


def _messages(system: Optional[str], prompt: str) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


async def chat(
    provider: Any,
    prompt: str,
    *,
    system: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Drain a provider's ``chat_stream`` and return the concatenated text.

    Args:
        provider: Object with an async ``chat_stream(messages, ...)`` generator
            yielding ``(event_type, payload)`` tuples.
        prompt:   The user-turn text (ignored if ``messages`` is given).
        system:   Optional system prompt prepended when ``messages`` is None.
        messages: Full transcript override; wins over ``prompt``/``system``.

    Returns:
        The model's reply as text. May be empty if the model only emitted
        tool events — skills that need structured output should validate.

    Raises:
        RuntimeError: If the provider signalled an error event, or the object
            does not expose a usable ``chat_stream``.
    """
    stream_factory = getattr(provider, "chat_stream", None)
    if stream_factory is None or not callable(stream_factory):
        raise RuntimeError(
            f"provider {type(provider).__name__} does not expose chat_stream; "
            "skills need a provider compatible with nexa.provider.LLMProvider"
        )

    transcript = messages if messages is not None else _messages(system, prompt)

    text_parts: List[str] = []
    errors: List[str] = []

    agen = stream_factory(transcript)
    # chat_stream is an async generator function; calling it returns the agen.
    if callable(getattr(agen, "__aiter__", None)) or hasattr(agen, "__aiter__"):
        pass  # already an async generator
    else:  # a coroutine returning an async generator (some fakes) — await it
        agen = await agen

    async for event_type, payload in agen:
        # Ornith/llama.cpp can put tokens under "reasoning"/"thinking" when
        # --reasoning-preserve is active — capture those too so skills don't
        # see an empty reply from a working model.
        if event_type in ("token", "reasoning", "thinking", "content"):
            text_parts.append(str(payload))
        elif event_type == "error":
            errors.append(str(payload))
        elif event_type == "done":
            break
        # tool_call and any other events are irrelevant to a text completion.

    if errors:
        raise RuntimeError("LLM error: " + "; ".join(errors))
    return "".join(text_parts)


async def chat_text(provider: Any, prompt: str, *, system: Optional[str] = None) -> str:
    """Alias for :func:`chat` kept for handler readability."""
    return await chat(provider, prompt, system=system)


async def chat_json(
    provider: Any,
    prompt: str,
    *,
    system: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ask the model for a JSON object and parse it tolerantly.

    The parser strips a leading/trailing markdown fence and locates the first
    balanced ``{...}`` block, so mildly chatty models still yield usable data.

    Raises:
        ValueError: If no JSON object could be recovered from the reply.
    """
    raw = await chat(provider, prompt, system=system)
    return parse_json_object(raw)


def parse_json_object(raw: str) -> Dict[str, Any]:
    """
    Extract the first balanced top-level JSON object from ``raw``.

    Tolerates `````json fences and prose around the object. Raises
    :class:`ValueError` when nothing parseable is found.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Drop an opening fence like ```json or ``` and its line.
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: text.rstrip().rfind("```")]

    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model reply")

    depth = 0
    in_string = False
    escape = False
    last_close = -1  # index where depth returns to 0, or last '}' seen
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            last_close = i
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"unparseable JSON in model reply: {exc}") from exc
                if not isinstance(parsed, dict):
                    raise ValueError("model JSON is not an object")
                return parsed

    # Repair path: the model likely truncated. Try closing an unterminated
    # string then re-balancing open braces/brackets. Local models with a small
    # token cap end mid-string often enough that an honest "best effort parse"
    # beats a hard failure — and any residual garbage fails schema validation
    # honestly downstream anyway.
    fragment = text[start:]
    if in_string:
        fragment += '"'
    closers = ("}" * fragment.count("{")) + ("]" * fragment.count("["))
    fragment += closers
    fragment = fragment.replace("}", "}", 1)  # no-op clarity
    # try progressively trimming from the end to the last valid structure
    for trim in range(0, len(fragment)):
        candidate = fragment[: len(fragment) - trim]
        if not candidate.strip().endswith(("}", "]")):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed:
            return parsed
    raise ValueError("no balanced JSON object found in model reply, even after repair")
