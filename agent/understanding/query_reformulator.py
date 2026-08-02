"""
Nexa Agent — Query Reformulator
================================

Reformulates a user's vague or ambiguous question into one or more
precise search queries. This dramatically improves web search recall
because the LLM/user often uses casual phrasing that search engines
handle poorly.

Examples:
    "what's the latest from openai" →
        ["OpenAI latest news", "OpenAI announcement latest", "OpenAI blog"]

The reformulator is rule-based + lightweight (no LLM call).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Stopwords to strip when forming search queries.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at",
    "to", "for", "with", "and", "or", "but", "do", "does", "did", "can",
    "could", "would", "should", "will", "what", "who", "when", "where",
    "why", "how", "i", "you", "we", "they", "he", "she", "it", "this",
    "that", "these", "those", "me", "my", "your",
}

# Freshness hints → suffix added to the query.
_FRESHNESS_HINTS = ("latest", "newest", "recent", "current", "today", "now")
_FRESHNESS_SUFFIX = "latest"

# Opinion hints → suffix.
_OPINION_HINTS = ("best", "recommend", "compare", "vs", "versus")
_OPINION_SUFFIX = "comparison review"


@dataclass
class ReformulatedQuery:
    """
    The result of reformulating a user question.

    Attributes:
        original:      The original user message.
        queries:       The reformulated search queries (1–3).
        intent:        Detected search intent (``"factual"``, ``"freshness"``,
                       ``"opinion"``).
        keywords:      Extracted keywords.
    """

    original: str
    queries: List[str] = field(default_factory=list)
    intent: str = "factual"
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "original": self.original,
            "queries": self.queries,
            "intent": self.intent,
            "keywords": self.keywords,
        }


def extract_keywords(message: str) -> List[str]:
    """
    Extract meaningful keywords from ``message``.

    Args:
        message: The raw user message.

    Returns:
        A list of keywords (lowercase, stopwords removed).
    """
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9.+-]*\b", message)
    return [t.lower() for t in tokens if t.lower() not in _STOPWORDS and len(t) > 1]


def detect_intent(message: str) -> str:
    """
    Detect the search intent of ``message``.

    Returns one of ``"freshness"``, ``"opinion"``, ``"factual"``.
    """
    msg_lower = message.lower()
    if any(h in msg_lower for h in _FRESHNESS_HINTS):
        return "freshness"
    if any(h in msg_lower for h in _OPINION_HINTS):
        return "opinion"
    return "factual"


def reformulate(message: str, max_queries: int = 3) -> ReformulatedQuery:
    """
    Reformulate ``message`` into one or more precise search queries.

    Args:
        message:     The raw user message.
        max_queries: Max number of queries to produce (1–3).

    Returns:
        A :class:`ReformulatedQuery`.
    """
    message = message.strip()
    intent = detect_intent(message)
    keywords = extract_keywords(message)
    if not keywords:
        return ReformulatedQuery(original=message, queries=[message], intent=intent)

    # Build the core query (all keywords, in original order of appearance).
    core = " ".join(keywords[:6])

    # Build alternate queries.
    queries: List[str] = [core]
    if intent == "freshness":
        queries.append(f"{core} {_FRESHNESS_SUFFIX}")
        queries.append(f"{core} news")
    elif intent == "opinion":
        queries.append(f"{core} {_OPINION_SUFFIX}")
        queries.append(f"best {core}")
    else:
        # Factual: produce a longer variant + a short variant.
        short = " ".join(keywords[:3])
        if short != core:
            queries.append(short)
        long = " ".join(keywords[:8])
        if long != core:
            queries.append(long)

    # Dedup while preserving order, cap to max_queries.
    seen: set = set()
    unique: List[str] = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique.append(q)
    return ReformulatedQuery(
        original=message,
        queries=unique[:max_queries],
        intent=intent,
        keywords=keywords,
    )


def pick_best_query(rq: ReformulatedQuery) -> str:
    """
    Pick the single best query from a :class:`ReformulatedQuery`.

    The "best" query is the first one (the core keywords + optional suffix).

    Args:
        rq: The reformulated query.

    Returns:
        The best single query string.
    """
    return rq.queries[0] if rq.queries else rq.original
