"""
OpenForge — fact_checking skill (web_research)
===============================================

Purpose
-------
Check the truth of a ``claim`` against optionally supplied ``sources``.
Returns the manifest contract: ``verdict`` (true | false | partial |
unverified), ``evidence`` (list of str) and ``confidence`` (number 0..1).

Permissions
-----------
Declared: ``network:*``, ``memory:read``. NOTE: this handler currently uses
NO network search tool — it evaluates the claim only against the sources the
caller provides, via the provider model.

Honesty note
------------
Because no live retrieval is performed inside this skill, a claim submitted
WITHOUT verifiable sources honestly yields the ``"unverified"`` verdict (the
model is instructed to return exactly that rather than guess from memory).
Only when real source texts are supplied can the model reason a
true/false/partial verdict, and its ``evidence`` must quote or paraphrase
those provided sources — the prompt forbids fabricated citations. The verdict
is normalised against the manifest enum (anything unrecognised becomes
``"unverified"``) and ``confidence`` is coerced and clamped into [0, 1].
LLM errors and unparseable JSON propagate to the caller.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from skills._common import ask_llm_json, as_list, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle", "SYSTEM"]

_VERDICTS = ("true", "false", "partial", "unverified")

SYSTEM = (
    "You are a rigorous fact-checking engine inside the OpenForge skills "
    "system. Evaluate the user's claim ONLY against the source texts provided "
    "in the prompt. Rules:\n"
    "- If no sources are provided, or the provided sources do not actually "
    'bear on the claim, the verdict MUST be "unverified" — never guess from '
    "memory or prior belief.\n"
    "- Evidence entries must quote or closely paraphrase the PROVIDED sources. "
    "Never fabricate citations, URLs, studies, or quotes.\n"
    "Respond with a single JSON object and nothing else — no prose, no "
    "markdown fence. The object MUST have these keys:\n"
    '  "verdict": one of "true", "false", "partial", or "unverified";\n'
    '  "evidence": array of strings — each grounded in a provided source, or '
    "empty when unverified;\n"
    '  "confidence": number from 0.0 to 1.0 reflecting how strongly the '
    "provided sources support the verdict."
)


def _build_prompt(claim: str, sources: List[str]) -> str:
    """Embed the real claim and any caller-supplied source texts."""
    lines = [f"Claim under review: {claim}", ""]
    if sources:
        lines.append("Provided sources (evaluate strictly against these):")
        for i, src in enumerate(sources, 1):
            lines.append(f"[{i}] {src}")
    else:
        lines.append(
            "No sources were provided. Per your rules, the verdict for this "
            'claim is "unverified" with empty evidence and low confidence.'
        )
    return "\n".join(lines)


async def handle(input_data: dict, provider) -> dict:
    """
    Fact-check ``input_data['claim']`` and return the verdict contract.

    Raises:
        SkillInputError: Missing, wrongly-typed, or empty ``claim``.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    claim = require(input_data, "claim", str, "claim to verify")
    if not claim.strip():
        raise SkillInputError("field 'claim' must be a non-empty string")

    raw_sources = input_data.get("sources")
    if raw_sources is not None and not isinstance(raw_sources, list):
        raise SkillInputError(
            f"field 'sources' must be array, got {type(raw_sources).__name__}"
        )
    sources = [s for s in (coerce_str(x).strip() for x in as_list(raw_sources)) if s]

    data = await ask_llm_json(provider, _build_prompt(claim, sources), system=SYSTEM)

    verdict = coerce_str(data.get("verdict"), default="unverified").strip().lower()
    if verdict not in _VERDICTS:
        verdict = "unverified"
    confidence = max(0.0, min(1.0, coerce_number(data.get("confidence"), default=0.0)))
    evidence = [e for e in (coerce_str(x).strip() for x in as_list(data.get("evidence"))) if e]

    if verdict == "unverified":
        # An unverified verdict cannot honestly carry supporting evidence.
        evidence = []

    return {"verdict": verdict, "evidence": evidence, "confidence": confidence}
