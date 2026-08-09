"""
OpenForge — Autonomous Web Learner
==================================

This module lets Forge learn facts *on its own* — without being explicitly
asked — by detecting knowledge gaps in the user's question and proactively
running web searches to fill them.

How it works:
    1. :func:`detect_knowledge_gap` scans the user's message for entities
       the agent has never seen (or hasn't seen recently).
    2. :func:`should_auto_learn` decides whether a search is worthwhile
       (respects a per-session budget to avoid runaway searches).
    3. :func:`learn_about` runs a web search and stores the result in the
       :class:`KnowledgeCache` and the long-term memory store.
    4. :func:`enrich_with_learned_facts` injects relevant cached facts into
       the system prompt so the LLM has grounded context.

The learner is **opt-in** via ``FORGE_AUTONOMOUS_LEARNING=1`` and is throttled
by a configurable per-session budget so it never floods the user with
unexpected network calls.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Keyword hints that strongly suggest the user wants fresh information.
FRESHNESS_HINTS: Tuple[str, ...] = (
    "latest", "newest", "recent", "current", "today", "now", "2024", "2025",
    "2026", "update", "news", "happen", "release", "announce", "launch",
)

# Topics that should always trigger a fact-check (high-stakes domains).
FACT_CHECK_TRIGGERS: Tuple[str, ...] = (
    "president", "ceo", "ceo of", "winner", "result", "score",
    "price of", "stock", "weather", "population of",
)

# Cap of autonomous searches per session to avoid runaway costs.
DEFAULT_SESSION_BUDGET: int = 5

# Minimum seconds between two autonomous searches (rate limiter).
DEFAULT_COOLDOWN_SECONDS: float = 60.0


@dataclass
class LearningBudget:
    """
    Per-session budget for autonomous learning.

    Attributes:
        max_searches:   Hard cap on autonomous searches this session.
        used:           Number of searches performed so far.
        last_search_at: Monotonic timestamp of the last search (rate limit).
        enabled:        Master switch (env-driven).
    """

    max_searches: int = DEFAULT_SESSION_BUDGET
    used: int = 0
    last_search_at: float = 0.0
    enabled: bool = field(default_factory=lambda: _env_flag("FORGE_AUTONOMOUS_LEARNING"))

    @property
    def remaining(self) -> int:
        """Return how many autonomous searches are left."""
        return max(0, self.max_searches - self.used)

    @property
    def can_search(self) -> bool:
        """Return ``True`` if a search is allowed right now."""
        if not self.enabled:
            return False
        if self.remaining <= 0:
            return False
        # Rate limit: at least DEFAULT_COOLDOWN_SECONDS since last search.
        elapsed = time.monotonic() - self.last_search_at
        return elapsed >= DEFAULT_COOLDOWN_SECONDS

    def consume(self) -> None:
        """Mark one search as used."""
        self.used += 1
        self.last_search_at = time.monotonic()


def _env_flag(name: str) -> bool:
    """Read a boolean env flag (default ``False``)."""
    return os.environ.get(name, "0").lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------
# Pattern for capitalized multi-word entities (proper nouns, product names, etc.).
_ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b")

# Stopwords to ignore when an "entity" is really just sentence-start words.
_STOPWORDS = {
    "The", "A", "An", "I", "You", "We", "They", "He", "She", "It",
    "This", "That", "These", "Those", "What", "How", "Why", "When",
    "Where", "Who", "Is", "Are", "Was", "Were", "Do", "Does", "Did",
    "Can", "Could", "Should", "Would", "Will", "Have", "Has", "Had",
    "Forge", "Hello", "Hi", "Hey", "Thanks", "Thank",
    "Tell", "Me", "About", "Please", "From", "For", "With", "And",
    "Or", "But", "Of", "In", "On", "At", "To",
}


def detect_knowledge_gap(
    user_message: str,
    known_entities: Optional[set] = None,
) -> List[str]:
    """
    Detect entities in the user message that the agent hasn't seen before.

    Args:
        user_message:   The raw user message.
        known_entities: Set of entity names already known (case-insensitive).

    Returns:
        A de-duplicated list of unknown entities (preserving original casing).
    """
    known = {e.lower() for e in (known_entities or set())}
    candidates: List[str] = []
    seen_lower: set = set()
    for match in _ENTITY_PATTERN.finditer(user_message):
        entity = match.group(0).strip()
        if entity in _STOPWORDS:
            continue
        if len(entity) < 3:
            continue
        low = entity.lower()
        if low in seen_lower or low in known:
            continue
        seen_lower.add(low)
        candidates.append(entity)
    return candidates[:5]  # cap at 5 to stay focused


def should_auto_learn(
    user_message: str,
    budget: LearningBudget,
    known_entities: Optional[set] = None,
) -> Optional[str]:
    """
    Decide whether to trigger an autonomous web search.

    Returns:
        The search query to run, or ``None`` if no search is warranted.

    The decision considers:
        - Whether autonomous learning is enabled and budget remains.
        - Whether the message contains freshness hints or fact-check triggers.
        - Whether there are unknown entities worth learning about.
    """
    if not budget.can_search:
        return None

    msg_lower = user_message.lower()

    # High-priority: fact-check triggers (always search if budget allows).
    for trigger in FACT_CHECK_TRIGGERS:
        if trigger in msg_lower:
            gaps = detect_knowledge_gap(user_message, known_entities)
            if gaps:
                return f"{gaps[0]} {trigger}"
            return trigger.strip()

    # Medium-priority: freshness hints + unknown entities.
    has_freshness = any(h in msg_lower for h in FRESHNESS_HINTS)
    gaps = detect_knowledge_gap(user_message, known_entities)
    if has_freshness and gaps:
        return f"{gaps[0]} {next(h for h in FRESHNESS_HINTS if h in msg_lower)}"

    # Low-priority: a single very specific unknown entity (>=2 words).
    specific = [g for g in gaps if " " in g]
    if specific:
        return specific[0]

    return None


# ---------------------------------------------------------------------------
# Learning action
# ---------------------------------------------------------------------------
@dataclass
class LearnedFact:
    """
    A fact learned autonomously from the web.

    Attributes:
        query:       The search query that produced this fact.
        entity:      The primary entity the fact is about.
        summary:     Short human-readable summary (≤ 300 chars).
        source_url:  Best source URL (for citation).
        source_title:Title of the source page.
        learned_at:  Unix timestamp when the fact was stored.
        confidence:  0.0–1.0 heuristic confidence score.
    """

    query: str
    entity: str
    summary: str
    source_url: str = ""
    source_title: str = ""
    learned_at: float = field(default_factory=time.time)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (for JSON storage)."""
        return {
            "query": self.query,
            "entity": self.entity,
            "summary": self.summary,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "learned_at": self.learned_at,
            "confidence": self.confidence,
        }


async def learn_about(
    query: str,
    budget: LearningBudget,
    web_search_fn,
    cache=None,
) -> Optional[LearnedFact]:
    """
    Run a web search and store the result as a :class:`LearnedFact`.

    This is a thin orchestrator: the actual web search is injected via
    ``web_search_fn`` so the learner is decoupled from the network layer
    (and easily testable with a mock).

    Args:
        query:          The search query.
        budget:         The session learning budget (will be consumed).
        web_search_fn:  Async callable ``async def (query: str) -> list[dict]``
                        returning search results (each with ``title``,
                        ``url``, ``snippet``).
        cache:          Optional :class:`~agent.knowledge_cache.KnowledgeCache`
                        to store the learned fact.

    Returns:
        The :class:`LearnedFact` if learning succeeded, else ``None``.
    """
    if not budget.can_search:
        return None

    try:
        results = await web_search_fn(query)
    except Exception:
        return None
    finally:
        # Always consume the budget even on partial failure, so a flaky
        # network doesn't cause a retry storm.
        budget.consume()

    if not results:
        return None

    top = results[0]
    snippet = top.get("snippet", "") or top.get("title", "")
    summary = (snippet[:300] + "…") if len(snippet) > 300 else snippet

    fact = LearnedFact(
        query=query,
        entity=query.split()[0] if query else "",
        summary=summary,
        source_url=top.get("url", ""),
        source_title=top.get("title", ""),
        confidence=min(1.0, 0.4 + 0.15 * min(3, len(results))),
    )

    if cache is not None:
        try:
            cache.store(fact)
        except Exception:
            pass

    return fact


def enrich_with_learned_facts(
    facts: List[LearnedFact],
    max_facts: int = 5,
) -> str:
    """
    Build a short context block from learned facts to inject into the prompt.

    Args:
        facts:     The learned facts (most-recent first).
        max_facts: Maximum number of facts to include.

    Returns:
        A formatted string suitable for the system prompt, or ``""`` if empty.
    """
    if not facts:
        return ""
    lines: List[str] = ["Recently learned facts (autonomous web research):"]
    for f in facts[:max_facts]:
        cite = f" (source: {f.source_title})" if f.source_title else ""
        lines.append(f"- {f.entity}: {f.summary}{cite}")
    return "\n".join(lines)
