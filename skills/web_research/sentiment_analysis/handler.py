"""
OpenForge — sentiment_analysis skill (web_research)
====================================================

Purpose
-------
Analyse the sentiment of ``text`` at a ``detail_level`` of basic or detailed.
Returns the manifest contract: ``sentiment`` (positive | negative | neutral),
``score`` (number in [-1.0, 1.0]), ``emotions`` (list of {emotion, intensity})
and ``intent`` (str).

Permissions
-----------
Declared: ``memory:read``. This skill touches no filesystem and no network —
it operates purely on the inline ``text`` payload via the provider model.

Honesty note
------------
``sentiment``, ``score``, ``emotions`` and ``intent`` all come from the
model's reading of the REAL input text, which is embedded verbatim in the
prompt. This handler only normalises: the sentiment label is lowercased and
any value outside the manifest enum falls back to ``"neutral"``; ``score``
and each emotion ``intensity`` are coerced to numbers and clamped into their
schema ranges. Nothing is ever invented locally — if the model is silent the
result is the neutral/empty schema-valid default, and LLM errors or
unparseable JSON propagate to the caller.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from skills._common import ask_llm_json, as_list, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle", "SYSTEM"]

_SENTIMENTS = ("positive", "negative", "neutral")
_DETAIL_LEVELS = ("basic", "detailed")

SYSTEM = (
    "You are a sentiment analysis engine inside the Nexa Agent skills "
    "system. Analyse the sentiment of the user's text at the requested "
    "detail level (basic or detailed). Base your judgement only on the given "
    "text — never assume context that is not present. Respond with a single "
    "JSON object and nothing else — no prose, no markdown fence. The object "
    "MUST have these keys:\n"
    '  "sentiment": one of "positive", "negative", or "neutral";\n'
    '  "score": number from -1.0 (very negative) to 1.0 (very positive);\n'
    '  "emotions": array of objects, each {"emotion": string, "intensity": '
    "number from 0.0 to 1.0};\n"
    '  "intent": string — a short description of what the author is trying '
    "to achieve."
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalise_emotions(raw: Any) -> List[Dict[str, Any]]:
    """Coerce model output into [{emotion: str, intensity: 0..1}, ...]."""
    emotions: List[Dict[str, Any]] = []
    for item in as_list(raw):
        if not isinstance(item, dict):
            name = coerce_str(item).strip()
            if not name:
                continue
            emotions.append({"emotion": name, "intensity": 0.5})
            continue
        name = coerce_str(item.get("emotion")).strip()
        if not name:
            continue
        intensity = _clamp(coerce_number(item.get("intensity"), default=0.5), 0.0, 1.0)
        emotions.append({"emotion": name, "intensity": intensity})
    return emotions


async def handle(input_data: dict, provider) -> dict:
    """
    Analyse ``input_data['text']`` and return the sentiment contract.

    Raises:
        SkillInputError: Missing or wrongly-typed ``text``.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    text = require(input_data, "text", str, "text to analyse")
    if not text.strip():
        raise SkillInputError("field 'text' must be a non-empty string")

    detail_level = coerce_str(
        input_data.get("detail_level"), default="basic"
    ).strip().lower()
    if detail_level not in _DETAIL_LEVELS:
        detail_level = "basic"

    prompt = f"Detail level: {detail_level}\nText to analyse (verbatim):\n{text}"
    data = await ask_llm_json(provider, prompt, system=SYSTEM)

    sentiment = coerce_str(data.get("sentiment"), default="neutral").strip().lower()
    if sentiment not in _SENTIMENTS:
        sentiment = "neutral"
    score = _clamp(coerce_number(data.get("score"), default=0.0), -1.0, 1.0)

    return {
        "sentiment": sentiment,
        "score": score,
        "emotions": _normalise_emotions(data.get("emotions")),
        "intent": coerce_str(data.get("intent"), default=""),
    }
