"""
Nexa Agent — Pattern Recognizer
=============================

Detects recurring patterns in the user's conversation history so the
agent can anticipate needs and pre-warm tools. Patterns tracked:

    - Recurring topics (the user keeps asking about the same subject).
    - Recurring tools used per topic.
    - Time-of-day activity patterns (optional, lightweight).
    - Phrasing habits (terse vs verbose).

The recognizer is intentionally cheap (regex + counters, no LLM call).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Topic keywords (case-insensitive) → topic label.
TOPIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "code": ("code", "function", "bug", "error", "fix", "implement", "python", "javascript"),
    "research": ("search", "find", "research", "latest", "news", "article"),
    "writing": ("write", "draft", "essay", "document", "email", "summary"),
    "data": ("data", "csv", "json", "database", "query", "analyze"),
    "system": ("config", "install", "deploy", "server", "docker"),
    "learning": ("explain", "teach", "learn", "tutorial", "understand"),
}


@dataclass
class PatternReport:
    """
    Result of analyzing conversation patterns.

    Attributes:
        top_topics:    Most-frequent topics (label, count) sorted desc.
        avg_msg_length:Average user message word count.
        terse_ratio:   Fraction of messages ≤ 5 words.
        tool_per_topic:Most-used tool per topic.
        suggestions:   Human-readable suggestions derived from patterns.
    """

    top_topics: List[Tuple[str, int]] = field(default_factory=list)
    avg_msg_length: float = 0.0
    terse_ratio: float = 0.0
    tool_per_topic: Dict[str, str] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "top_topics": self.top_topics,
            "avg_msg_length": round(self.avg_msg_length, 2),
            "terse_ratio": round(self.terse_ratio, 3),
            "tool_per_topic": self.tool_per_topic,
            "suggestions": self.suggestions,
        }


class PatternRecognizer:
    """
    Stateful pattern recognizer.

    Call :meth:`observe` for every user message + the tools used in that
    turn. At any point, call :meth:`report` for a snapshot.
    """

    def __init__(self) -> None:
        self._topic_counter: Counter = Counter()
        self._tool_per_topic: Dict[str, Counter] = {}
        self._msg_lengths: List[int] = []
        self._terse_count: int = 0
        self._total_msgs: int = 0

    def observe(
        self,
        message: str,
        tools_used: Optional[List[str]] = None,
    ) -> None:
        """
        Record one user message and the tools used in that turn.

        Args:
            message:    The raw user message.
            tools_used:  List of tool names invoked in this turn.
        """
        self._total_msgs += 1
        words = len(message.split())
        self._msg_lengths.append(words)
        if words <= 5:
            self._terse_count += 1

        topics = self._detect_topics(message)
        for topic in topics:
            self._topic_counter[topic] += 1
            if tools_used:
                if topic not in self._tool_per_topic:
                    self._tool_per_topic[topic] = Counter()
                for t in tools_used:
                    self._tool_per_topic[topic][t] += 1

    @staticmethod
    def _detect_topics(message: str) -> List[str]:
        """Return the topics mentioned in ``message``."""
        msg_lower = message.lower()
        found: List[str] = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(k in msg_lower for k in keywords):
                found.append(topic)
        return found

    def report(self) -> PatternReport:
        """Build a :class:`PatternReport` from observed data."""
        top = self._topic_counter.most_common(5)
        avg_len = (
            sum(self._msg_lengths) / len(self._msg_lengths)
            if self._msg_lengths
            else 0.0
        )
        terse = self._terse_count / self._total_msgs if self._total_msgs else 0.0

        tool_per_topic: Dict[str, str] = {}
        for topic, counter in self._tool_per_topic.items():
            if counter:
                tool_per_topic[topic] = counter.most_common(1)[0][0]

        suggestions = self._build_suggestions(top, terse, avg_len, tool_per_topic)
        return PatternReport(
            top_topics=top,
            avg_msg_length=avg_len,
            terse_ratio=terse,
            tool_per_topic=tool_per_topic,
            suggestions=suggestions,
        )

    @staticmethod
    def _build_suggestions(
        top: List[Tuple[str, int]],
        terse: float,
        avg_len: float,
        tool_per_topic: Dict[str, str],
    ) -> List[str]:
        out: List[str] = []
        if top:
            out.append(f"User often asks about: {top[0][0]} — pre-warm relevant tools.")
        if terse > 0.5:
            out.append("User tends to write terse messages — use the prompt expander.")
        if avg_len > 30:
            out.append("User writes verbose messages — summarize before processing.")
        for topic, tool in tool_per_topic.items():
            out.append(f"For '{topic}' tasks, the user typically needs: {tool}.")
        return out

    def reset(self) -> None:
        """Clear all observed data."""
        self._topic_counter.clear()
        self._tool_per_topic.clear()
        self._msg_lengths.clear()
        self._terse_count = 0
        self._total_msgs = 0
