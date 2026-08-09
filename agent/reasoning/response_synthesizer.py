"""
OpenForge — Response Synthesizer
================================

When the agent gathers information from multiple sources (multiple tool
calls, web search results, memory items), the final answer should
**synthesize** them into one coherent response rather than just
concatenating raw outputs.

This module provides:
    - :func:`synthesize` — merge multiple partial answers into one.
    - :func:`deduplicate_facts` — drop near-duplicate facts.
    - :func:`reconcile_conflicts` — detect + flag conflicting facts.

All operations are pure-Python (no LLM call) so they're fast and cheap.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Sentence splitter (cheap; not perfect but adequate for synthesis).
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class SynthesisResult:
    """
    Result of synthesizing multiple partial answers.

    Attributes:
        text:        The synthesized answer.
        sources:     Number of distinct sources used.
        conflicts:   Detected conflicts (list of strings).
        deduped:     Number of duplicate facts removed.
    """

    text: str
    sources: int = 0
    conflicts: List[str] = field(default_factory=list)
    deduped: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "text": self.text,
            "sources": self.sources,
            "conflicts": self.conflicts,
            "deduped": self.deduped,
        }


def _normalize_fact(text: str) -> str:
    """Normalize a fact for dedup comparison."""
    norm = re.sub(r"\s+", " ", text).strip().lower()
    # Drop articles + punctuation for fuzzy matching.
    norm = re.sub(r"[^a-z0-9 ]+", "", norm)
    return norm


def deduplicate_facts(facts: Sequence[str]) -> tuple:
    """
    Remove near-duplicate facts.

    Args:
        facts: List of fact strings.

    Returns:
        A tuple ``(unique_facts, num_removed)``.
    """
    seen: set = set()
    unique: List[str] = []
    removed = 0
    for f in facts:
        norm = _normalize_fact(f)
        if not norm:
            continue
        if norm in seen:
            removed += 1
            continue
        seen.add(norm)
        unique.append(f)
    return unique, removed


def reconcile_conflicts(facts: Sequence[str]) -> List[str]:
    """
    Detect conflicting numeric/date facts.

    Two facts "conflict" if they share the same subject keyword but
    quote different numbers.

    Args:
        facts: List of fact strings.

    Returns:
        A list of human-readable conflict descriptions.
    """
    conflicts: List[str] = []
    # Extract (subject, number) pairs.
    pairs: List[tuple] = []
    for f in facts:
        # Subject = first few words; number = first number found.
        m_num = re.search(r"\b(\d[\d.,]*)\b", f)
        if not m_num:
            continue
        words = f.split()[:4]
        subject = " ".join(words).lower()
        pairs.append((subject, m_num.group(1), f))
    # Compare pairs sharing the same subject.
    for i, (s1, n1, f1) in enumerate(pairs):
        for s2, n2, f2 in pairs[i + 1 :]:
            if s1 == s2 and n1 != n2:
                conflicts.append(
                    f"Conflict: '{f1}' vs '{f2}' (different numbers: {n1} vs {n2})"
                )
    return conflicts


def synthesize(
    parts: Sequence[str],
    intro: str = "",
    outro: str = "",
    max_sentences: int = 8,
) -> SynthesisResult:
    """
    Synthesize multiple partial answers into one coherent response.

    The synthesis:
        1. Splits each part into sentences.
        2. Deduplicates sentences (fuzzy).
        3. Reconciles conflicting numeric facts.
        4. Caps the result to ``max_sentences``.
        5. Wraps with optional intro/outro.

    Args:
        parts:         The partial answers to merge.
        intro:         Optional intro line prepended to the result.
        outro:         Optional outro line appended to the result.
        max_sentences: Maximum sentences in the final answer.

    Returns:
        A :class:`SynthesisResult`.
    """
    if not parts:
        return SynthesisResult(text=intro + outro, sources=0)

    # Collect all sentences.
    all_sentences: List[str] = []
    for part in parts:
        if not part:
            continue
        all_sentences.extend(s.strip() for s in _SENT_SPLIT.split(part) if s.strip())

    unique, removed = deduplicate_facts(all_sentences)
    conflicts = reconcile_conflicts(unique)

    # Cap to max_sentences (prefer the first N — they're usually the most central).
    trimmed = unique[:max_sentences]

    text_parts: List[str] = []
    if intro:
        text_parts.append(intro)
    text_parts.append(" ".join(trimmed))
    if outro:
        text_parts.append(outro)
    if conflicts:
        text_parts.append(
            "Note: some sources disagree on the following: "
            + "; ".join(conflicts[:3])
        )

    return SynthesisResult(
        text="\n\n".join(text_parts),
        sources=len(parts),
        conflicts=conflicts,
        deduped=removed,
    )


def summarize_tool_results(results: Iterable[Dict[str, Any]]) -> str:
    """
    Build a short prose summary from a list of tool results.

    Args:
        results: Iterable of ``{name, ok, output}`` dicts.

    Returns:
        A short human-readable summary.
    """
    items: List[str] = []
    for r in results:
        name = r.get("name", "tool")
        ok = r.get("ok", True)
        out = str(r.get("output", "")).strip()
        if not ok:
            items.append(f"- {name} failed: {out[:120]}")
        else:
            items.append(f"- {name}: {out[:120]}")
    if not items:
        return ""
    return "Tool results:\n" + "\n".join(items)
