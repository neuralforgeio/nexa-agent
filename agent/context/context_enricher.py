"""
OpenForge — Context Enricher
=============================

Enriches the LLM's context window with relevant prior information
before the model is called. Pulls from multiple sources:

    - Long-term memory (USER.md, MEMORY.md).
    - Knowledge cache (facts learned from the web).
    - Recent tool results (so the model sees what it just did).
    - Detected entities (to look up cached facts).

The enricher is cheap (no LLM call) and produces a single text block
suitable for the system prompt.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Regex for capitalized entities (proper nouns / product names).
_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b")
_STOPWORDS = {"The", "A", "An", "I", "You", "We", "They", "He", "She", "It",
              "This", "That", "Forge", "Hello", "Hi", "Hey"}


@dataclass
class EnrichedContext:
    """
    The enriched context block.

    Attributes:
        block:        The assembled text block for the system prompt.
        entities:     Entities detected in the user message.
        facts_used:   Cached facts included in the block.
        memory_used:  Long-term memory items included.
    """

    block: str = ""
    entities: List[str] = field(default_factory=list)
    facts_used: List[str] = field(default_factory=list)
    memory_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "block": self.block,
            "entities": self.entities,
            "facts_used": self.facts_used,
            "memory_used": self.memory_used,
        }


def detect_entities(message: str, max_entities: int = 5) -> List[str]:
    """
    Detect proper-noun entities in ``message``.

    Args:
        message:      The raw user message.
        max_entities: Maximum entities to return.

    Returns:
        A de-duplicated list of entity strings.
    """
    seen: set = set()
    out: List[str] = []
    for m in _ENTITY_RE.finditer(message):
        ent = m.group(0).strip()
        if ent in _STOPWORDS or len(ent) < 3:
            continue
        low = ent.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(ent)
    return out[:max_entities]


def enrich_context(
    user_message: str,
    user_profile: Optional[str] = None,
    long_term_memory: Optional[str] = None,
    knowledge_cache=None,
    recent_tool_results: Optional[List[Dict[str, Any]]] = None,
    max_facts: int = 3,
) -> EnrichedContext:
    """
    Build an enriched context block from all available sources.

    Args:
        user_message:         The current user message.
        user_profile:         Contents of USER.md (or similar).
        long_term_memory:     Contents of MEMORY.md (or similar).
        knowledge_cache:      Optional :class:`~agent.knowledge_cache.KnowledgeCache`.
        recent_tool_results:  List of ``{name, ok, output}`` dicts from this turn.
        max_facts:            Max cached facts to include.

    Returns:
        An :class:`EnrichedContext` with the assembled block.
    """
    entities = detect_entities(user_message)
    facts_used: List[str] = []
    memory_used: List[str] = []

    # Look up cached facts for detected entities.
    if knowledge_cache is not None and entities:
        for ent in entities:
            fact = knowledge_cache.fetch(ent)
            if fact is not None:
                facts_used.append(f"{ent}: {fact.summary}")
                if len(facts_used) >= max_facts:
                    break

    # Build the block.
    sections: List[str] = []

    if user_profile and user_profile.strip():
        memory_used.append("user profile")
        sections.append("--- User profile ---")
        sections.append(user_profile.strip())

    if long_term_memory and long_term_memory.strip():
        memory_used.append("long-term memory")
        sections.append("--- Long-term memory ---")
        sections.append(long_term_memory.strip())

    if facts_used:
        sections.append("--- Known facts (cached) ---")
        for f in facts_used:
            sections.append(f"- {f}")

    if recent_tool_results:
        sections.append("--- Recent tool results ---")
        for r in recent_tool_results[-5:]:
            name = r.get("name", "tool")
            ok = r.get("ok", True)
            out = str(r.get("output", "")).strip()[:200]
            status = "ok" if ok else "failed"
            sections.append(f"- {name} ({status}): {out}")

    if entities and not facts_used:
        sections.append(f"--- Entities in this message (no cached facts) ---")
        sections.append(", ".join(entities))

    block = "\n\n".join(sections) if sections else ""
    return EnrichedContext(
        block=block,
        entities=entities,
        facts_used=facts_used,
        memory_used=memory_used,
    )
