"""
Nexa Agent — Memory Consolidator
================================

Periodically consolidates the raw memory store into a compact, deduplicated
summary. Raw memories accumulate over time; the consolidator merges
near-duplicates, promotes high-confidence items, and demotes stale ones.

Consolidation is **idempotent** — running it twice produces the same
output as running it once.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

# Minimum confidence to be promoted to the consolidated store.
PROMOTION_THRESHOLD: float = 0.6

# After this many days, low-confidence memories are pruned.
STALE_DAYS: float = 30.0


@dataclass
class ConsolidationReport:
    """
    Result of a consolidation pass.

    Attributes:
        input_count:     Memories examined.
        output_count:    Memories after consolidation.
        merged:          Number of duplicates merged.
        promoted:        Number of high-confidence items promoted.
        pruned:          Number of stale/low-confidence items pruned.
    """

    input_count: int = 0
    output_count: int = 0
    merged: int = 0
    promoted: int = 0
    pruned: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "merged": self.merged,
            "promoted": self.promoted,
            "pruned": self.pruned,
        }


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    norm = re.sub(r"\s+", " ", text).strip().lower()
    norm = re.sub(r"[^a-z0-9 ]+", "", norm)
    return norm


def _word_overlap(a: str, b: str) -> float:
    """Return the Jaccard similarity of two strings' word sets."""
    sa = set(_normalize(a).split())
    sb = set(_normalize(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def consolidate_memories(
    memories: Iterable[Dict[str, Any]],
    dedup_threshold: float = 0.7,
) -> ConsolidationReport:
    """
    Consolidate a list of memory dicts.

    Each memory dict should have at least: ``content`` (str), optional
    ``confidence`` (float 0–1), ``kind`` (str), and ``created_at`` (unix ts).

    The function returns the report; **the caller is responsible for
    persisting** the surviving memories (use :func:`pick_survivors` to
    get the filtered list).

    Args:
        memories:        The memories to consolidate.
        dedup_threshold: Jaccard similarity above which two memories
                         are considered duplicates.

    Returns:
        A :class:`ConsolidationReport`.
    """
    mem_list = list(memories)
    report = ConsolidationReport(input_count=len(mem_list))

    survivors, merged = pick_survivors(mem_list, dedup_threshold)
    report.merged = merged

    # Promote + prune.
    promoted = 0
    pruned = 0
    now = time.time()
    final: List[Dict[str, Any]] = []
    for m in survivors:
        conf = float(m.get("confidence", 0.5))
        age_days = (now - float(m.get("created_at", now))) / 86400.0
        if conf >= PROMOTION_THRESHOLD:
            m = dict(m)
            m["promoted"] = True
            promoted += 1
            final.append(m)
        elif age_days > STALE_DAYS and conf < 0.3:
            pruned += 1
        else:
            final.append(m)

    report.output_count = len(final)
    report.promoted = promoted
    report.pruned = pruned
    return report


def pick_survivors(
    memories: List[Dict[str, Any]],
    dedup_threshold: float = 0.7,
) -> tuple:
    """
    Deduplicate memories by content similarity.

    Args:
        memories:        The memories to dedup.
        dedup_threshold: Jaccard similarity above which two memories
                         are considered duplicates.

    Returns:
        A tuple ``(survivors, num_merged)``.
    """
    survivors: List[Dict[str, Any]] = []
    merged = 0
    for m in memories:
        content = str(m.get("content", ""))
        is_dup = False
        for s in survivors:
            if _word_overlap(content, str(s.get("content", ""))) >= dedup_threshold:
                # Merge: bump confidence, take the higher of the two.
                s_conf = float(s.get("confidence", 0.5))
                m_conf = float(m.get("confidence", 0.5))
                s["confidence"] = max(s_conf, m_conf)
                s["occurrences"] = s.get("occurrences", 1) + 1
                merged += 1
                is_dup = True
                break
        if not is_dup:
            survivors.append(dict(m, occurrences=1))
    return survivors, merged


def build_consolidated_digest(memories: Iterable[Dict[str, Any]], max_items: int = 10) -> str:
    """
    Build a short digest of the highest-confidence memories.

    Args:
        memories:  The memories (post-consolidation).
        max_items: Maximum items in the digest.

    Returns:
        A formatted string, or ``""`` if empty.
    """
    mem_list = sorted(
        memories,
        key=lambda m: float(m.get("confidence", 0.5)),
        reverse=True,
    )
    if not mem_list:
        return ""
    lines: List[str] = ["Consolidated memory digest:"]
    for m in mem_list[:max_items]:
        content = str(m.get("content", "")).strip()
        kind = m.get("kind", "")
        conf = float(m.get("confidence", 0.5))
        prefix = f"[{kind}]" if kind else ""
        lines.append(f"- {prefix} {content} (conf={conf:.2f})")
    return "\n".join(lines)
