"""
OpenForge — Confidence Scorer
============================

Estimates how confident the agent should be in its own answer, based on
cheap heuristics (no LLM call). A low score triggers enrichment:
re-search, fact validation, or asking the user to clarify.

Signals used:
    - Length and specificity of the answer.
    - Whether tools were called and succeeded.
    - Whether sources were cited.
    - Whether hedging language ("maybe", "I think", "possibly") appears.
    - Whether the question was ambiguous.

The score is a float in ``[0.0, 1.0]``.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Hedging words lower confidence.
HEDGE_WORDS = (
    "maybe", "perhaps", "possibly", "i think", "i believe", "might be",
    "could be", "probably", "i'm not sure", "i am not sure", "unsure",
    "uncertain", "roughly", "approximately", "around", "guess",
)

# Specificity markers raise confidence.
SPECIFIC_MARKERS = (
    "according to", "source:", "data shows", "documented", "measured",
    "verified", "confirmed", "exactly", "precisely",
)


@dataclass
class ConfidenceReport:
    """
    Result of scoring an answer's confidence.

    Attributes:
        score:       Confidence in ``[0.0, 1.0]``.
        reasons:     Human-readable factors that influenced the score.
        should_enrich: ``True`` if score < 0.5 and enrichment is advised.
    """

    score: float
    reasons: List[str] = field(default_factory=list)
    should_enrich: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "should_enrich": self.should_enrich,
        }


def score_answer(
    answer: str,
    question: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    sources_cited: int = 0,
) -> ConfidenceReport:
    """
    Score the agent's confidence in ``answer``.

    Args:
        answer:       The assistant's answer text.
        question:     The original user question (for ambiguity check).
        tool_calls:   List of ``{name, ok}`` dicts (tools executed).
        sources_cited:Number of explicit citations in the answer.

    Returns:
        A :class:`ConfidenceReport`.
    """
    reasons: List[str] = []
    score = 0.5  # start neutral

    ans_lower = answer.lower()
    word_count = len(answer.split())

    # Factor 1: length/specificity.
    if word_count < 5:
        score -= 0.15
        reasons.append("answer is very short")
    elif word_count > 40:
        score += 0.1
        reasons.append("answer is substantive")

    # Factor 2: hedging language lowers confidence.
    hedge_hits = sum(1 for w in HEDGE_WORDS if w in ans_lower)
    if hedge_hits:
        score -= 0.1 * hedge_hits
        reasons.append(f"hedge language used ({hedge_hits}x)")

    # Factor 3: specificity markers raise confidence.
    spec_hits = sum(1 for m in SPECIFIC_MARKERS if m in ans_lower)
    if spec_hits:
        score += 0.08 * spec_hits
        reasons.append(f"specificity markers present ({spec_hits}x)")

    # Factor 4: tool calls (successful ones raise confidence).
    if tool_calls:
        ok = sum(1 for c in tool_calls if c.get("ok", False))
        total = len(tool_calls)
        if total and ok == total:
            score += 0.15
            reasons.append(f"all {total} tool call(s) succeeded")
        elif ok:
            score += 0.05
            reasons.append(f"{ok}/{total} tool calls succeeded")
        else:
            score -= 0.1
            reasons.append("all tool calls failed")

    # Factor 5: cited sources raise confidence.
    if sources_cited > 0:
        score += min(0.2, 0.1 * sources_cited)
        reasons.append(f"{sources_cited} source(s) cited")

    # Factor 6: ambiguous question lowers confidence.
    if question:
        q_lower = question.lower()
        ambiguous_markers = ("or what", "maybe", "not sure", "kind of", "sort of")
        if any(m in q_lower for m in ambiguous_markers):
            score -= 0.1
            reasons.append("question is ambiguous")

    # Clamp.
    score = max(0.0, min(1.0, score))
    should_enrich = score < 0.5
    return ConfidenceReport(
        score=score, reasons=reasons, should_enrich=should_enrich
    )


def should_fact_check(
    answer: str,
    score: float,
    threshold: float = 0.4,
) -> bool:
    """
    Decide whether a fact-check (web search validation) is warranted.

    Args:
        answer:   The answer text.
        score:    The confidence score.
        threshold:Score below which fact-checking is advised.

    Returns:
        ``True`` if fact-checking is recommended.
    """
    if score < threshold:
        return True
    # Always fact-check answers containing numbers/dates (high-stakes).
    if re.search(r"\b\d{4}\b|\b\d+%?\b", answer):
        return score < 0.6
    return False
