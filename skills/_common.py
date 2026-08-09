"""
OpenForge — shared building blocks for LLM-driven skills (v4.4.0)
==================================================================

Most Batch-8 skills follow the same shape: read some real input, build a
prompt, ask the model for a JSON object, normalise/validate it, return. This
module centralises that plumbing so 36 handlers stay small, consistent, and
testable — and so the honest-testing seams live in exactly one place.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ._llm import chat_json
from .registry import SkillInputError

__all__ = ["require", "ask_llm_json", "coerce_str", "coerce_number", "as_list"]


def require(data: Mapping[str, Any], field: str, kind: type, what: str = "") -> Any:
    """
    Fetch a required field, raising :class:`SkillInputError` on absence or a
    wrong primitive type. Handlers use this for a friendly 400-style message
    even though the registry's ``validate_schema`` already guards the boundary
    (``validate_schema`` runs first; ``require`` is defence-in-depth plus a
    clearer error for direct ``handle()`` callers).
    """
    if field not in data or data[field] is None:
        raise SkillInputError(f"missing required field {field!r}")
    value = data[field]
    if kind is int and isinstance(value, bool):
        raise SkillInputError(f"field {field!r} must be an integer")
    if not isinstance(value, kind):
        raise SkillInputError(
            f"field {field!r} must be {kind.__name__}, got {type(value).__name__}"
        )
    return value


async def ask_llm_json(
    provider: Any,
    prompt: str,
    *,
    system: str,
    fallback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ask the model for a JSON object and return it parsed.

    Args:
        provider: Provider passed to the handler.
        prompt:   Fully-built user prompt (already includes the real input).
        system:   System prompt that pins the output contract.
        fallback: When not None, a *copy* is returned if the model's reply is
            not parseable JSON. When None (default), a ValueError from the
            parser propagates so tests and callers see malformed output.

    Returns:
        The parsed JSON object.
    """
    result = await chat_json(provider, prompt, system=system)
    if not isinstance(result, dict):
        if fallback is not None:
            return dict(fallback)
        raise ValueError(f"model did not return a JSON object (got {type(result).__name__})")
    return result


def coerce_str(value: Any, default: str = "") -> str:
    """Best-effort str; never raises. Used to normalise LLM output."""
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def coerce_number(value: Any, default: float = 0.0) -> float:
    """Best-effort float for scores/confidences; never raises."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def as_list(value: Any) -> list:
    """Return value as a list (wrap scalars, pass through lists, [] for junk)."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]
