"""
Nexa Agent — Memory Curator (The "Getting Smarter" Loop)
========================================================

This module implements Nexa Agent's self-improvement system. After each
conversation turn, the curator analyzes the exchange and distills durable
insights into the memory store. Over time, the agent accumulates knowledge
about the user's preferences, effective problem-solving patterns, and
domain-specific facts — making it progressively smarter.

Inspired by ``memory_manager`` and ``curator`` modules —
original implementation.

Memory kinds:
    insight     — A reusable problem-solving insight.
    preference  — A user preference (e.g. "prefers concise answers").
    fact        — A durable fact about the user or their environment.
    skill       — A reusable prompt snippet / approach that worked well.

The curator runs the following pipeline after each turn:
    1. Extract candidate memories from the latest exchange.
    2. Deduplicate against existing memories (semantic similarity via FTS).
    3. Score and rank candidates by confidence.
    4. Store the top candidates in the memories table.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
from typing import Any, Dict, List, Optional

from nexa.state import ConversationDB


#: Memory kinds the curator can produce.
MEMORY_KINDS = ("insight", "preference", "fact", "skill")

#: Patterns that signal a memory-worthy statement.
_MEMORY_PATTERNS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:remember|note that|keep in mind|don't forget)\b.*", re.I), "preference"),
    (re.compile(r"\bI (?:prefer|like|want|need|always|never)\b.*", re.I), "preference"),
    (re.compile(r"\bmy (?:name|job|role|project|stack|language) is\b.*", re.I), "fact"),
    (re.compile(r"\bI (?:am|work|m developing|building|using)\b.*", re.I), "fact"),
    (re.compile(r"\b(?:the key|important|crucial|make sure to)\b.*", re.I), "insight"),
    (re.compile(r"\b(?:to fix|to solve|approach|strategy|method)\b.*", re.I), "skill"),
]

#: Max memories to store per turn.
MAX_MEMORIES_PER_TURN = 3


class MemoryCurator:
    """
    The self-improvement engine: distills conversation insights into
    durable memories.

    Attributes:
        db: The :class:`~storage.ConversationDB` for persistence.
    """

    def __init__(self, db: ConversationDB) -> None:
        """Initialize the curator with a database handle."""
        self.db = db

    async def curate_turn(
        self,
        user_input: str,
        assistant_answer: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze a completed turn and extract durable memories.

        This is the main entry point, called after each conversation turn.

        Args:
            user_input:      What the user said.
            assistant_answer: What the agent replied.
            tool_results:    Any tool results from the turn.

        Returns:
            A list of newly created memory dicts (empty if none extracted).
        """
        candidates = self._extract_candidates(user_input, assistant_answer, tool_results)
        if not candidates:
            return []

        # Deduplicate against existing memories.
        new_memories: List[Dict[str, Any]] = []
        for candidate in candidates:
            if await self._is_duplicate(candidate["content"]):
                continue
            mem_id = await self.db.add_memory(
                kind=candidate["kind"],
                content=candidate["content"],
                source="curator",
                confidence=candidate["confidence"],
            )
            new_memories.append(
                {
                    "id": mem_id,
                    "kind": candidate["kind"],
                    "content": candidate["content"],
                    "confidence": candidate["confidence"],
                }
            )
            if len(new_memories) >= MAX_MEMORIES_PER_TURN:
                break

        return new_memories

    def _extract_candidates(
        self, user_input: str, assistant_answer: str, tool_results: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract memory candidates from the user input and assistant answer.

        Uses pattern matching to identify memory-worthy statements.

        Args:
            user_input:      The user's message.
            assistant_answer: The agent's reply.
            tool_results:    Any tool results from the turn.

        Returns:
            A list of candidate dicts with 'kind', 'content', 'confidence'.
        """
        candidates: List[Dict[str, Any]] = []

        # Scan user input for explicit memory signals.
        for pattern, kind in _MEMORY_PATTERNS:
            matches = pattern.findall(user_input)
            for match in matches:
                text = match.strip()
                if len(text) < 10 or len(text) > 300:
                    continue
                candidates.append(
                    {
                        "kind": kind,
                        "content": text,
                        "confidence": 0.8 if kind == "preference" else 0.6,
                    }
                )

        # Detect successful tool usage patterns as "skills".
        if tool_results:
            for tr in tool_results:
                if tr.get("ok") and tr.get("tool"):
                    candidates.append(
                        {
                            "kind": "skill",
                            "content": f"Successfully used {tr['tool']} tool.",
                            "confidence": 0.5,
                        }
                    )

        # Detect insights in the assistant's answer (e.g. "The key is...").
        insight_matches = re.findall(
            r"(?:the key (?:is|to)|important (?:to|that)|make sure to)\s+[^.]+\.",
            assistant_answer,
            re.I,
        )
        for match in insight_matches[:1]:  # Max 1 insight per turn.
            candidates.append(
                {
                    "kind": "insight",
                    "content": match.strip(),
                    "confidence": 0.7,
                }
            )

        return candidates

    async def _is_duplicate(self, content: str) -> bool:
        """
        Check if a memory is semantically similar to an existing one.

        Uses FTS5 full-text search to find near-duplicates.

        Args:
            content: The candidate memory content.

        Returns:
            True if a similar memory already exists.
        """
        # Extract keywords from the content for FTS search.
        keywords = " ".join(content.split()[:5])
        if not keywords:
            return False
        try:
            existing = await self.db.search_memories(keywords, limit=1)
            if existing:
                # Check for high overlap.
                existing_content = existing[0]["content"].lower()
                new_content = content.lower()
                # Simple word-overlap heuristic.
                existing_words = set(existing_content.split())
                new_words = set(new_content.split())
                overlap = len(existing_words & new_words) / max(
                    len(new_words), 1
                )
                return overlap > 0.7
        except Exception:
            pass
        return False

    async def build_memory_digest(self, limit: int = 15) -> str:
        """
        Build a compact digest of current memories for the system prompt.

        This is injected into the system prompt so the agent "remembers"
        what it has learned across sessions.

        Args:
            limit: Max memories to include.

        Returns:
            A formatted string of memories, or empty string if none.
        """
        memories = await self.db.list_memories(limit=limit)
        if not memories:
            return ""

        lines = ["## Agent memories (accumulated knowledge)"]
        for m in memories:
            confidence_bar = "★" * int(m["confidence"] * 5) or "·"
            lines.append(
                f"- [{m['kind']}] {m['content']} ({confidence_bar}, used {m['times_used']}x)"
            )
        return "\n".join(lines)
