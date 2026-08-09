"""
OpenForge — translation skill (web_research)
=============================================

Purpose
-------
Translate a piece of inline text from a source language to a target
language, optionally guided by a domain/context hint. Returns the
manifest contract: ``translated_text`` (str), ``confidence`` (number,
0..1) and, when the model supplies it, ``detected_language`` (str).

Permissions
-----------
Declared: ``memory:read``. This skill touches no filesystem and needs no
workspace — it operates purely on the inline ``text`` payload.

Honesty note
------------
The translation itself is produced entirely by the provider model
(``provider.chat_stream``); this handler only builds the prompt, parses
the model's JSON reply, normalises the fields, and clamps ``confidence``
into [0, 1]. If the model is silent or wrong, there is no local
fabrication — missing required keys fall back to a schema-valid default
rather than an invented translation, and LLM/parse errors propagate to
the caller instead of being swallowed.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from skills._common import ask_llm_json, coerce_number, coerce_str, require

__all__ = ["handle", "SYSTEM"]

SYSTEM = (
    "You are a professional translator embedded in the Nexa Agent skills "
    "system. Translate the user's text exactly and fluently, preserving tone, "
    "register, formatting, and any domain terminology implied by the optional "
    "context hint. Respond with a single JSON object and nothing else — no "
    "prose, no markdown fence. The object MUST have these keys:\n"
    '  "translated_text": string  — the translation in the target language;\n'
    '  "detected_language": string — the ISO 639-1 code you detect for the '
    "source text (may differ from the declared source language);\n"
    '  "confidence": number — your confidence in the translation, from 0.0 '
    "to 1.0."
)


def _build_prompt(text: str, source: str, target: str, context: Optional[str]) -> str:
    """Embed the real input text, languages, and optional domain context."""
    lines = [
        f"Source language: {source}",
        f"Target language: {target}",
    ]
    if context:
        lines.append(f"Domain/context hint: {context}")
    lines.append("Text to translate (verbatim):")
    lines.append(text)
    return "\n".join(lines)


async def handle(input_data: dict, provider) -> dict:
    """
    Translate ``input_data['text']`` from ``from`` to ``to`` via the model.

    Raises:
        SkillInputError: Missing or wrongly-typed ``text``/``from``/``to``.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    text = require(input_data, "text", str, "text to translate")
    source = require(input_data, "from", str, "source language code")
    target = require(input_data, "to", str, "target language code")
    raw_context: Optional[str] = input_data.get("context")
    context = coerce_str(raw_context).strip() or None

    prompt = _build_prompt(text, source, target, context)
    data = await ask_llm_json(provider, prompt, system=SYSTEM)

    confidence = coerce_number(data.get("confidence"), default=0.5)
    confidence = max(0.0, min(1.0, confidence))

    result: Dict[str, Any] = {
        # No fabrication: if the model omitted it, the honest schema-valid
        # default is an empty string, never a locally invented translation.
        "translated_text": coerce_str(data.get("translated_text"), default=""),
        "confidence": confidence,
    }
    detected = coerce_str(data.get("detected_language"), default="").strip()
    if detected:
        result["detected_language"] = detected
    return result
