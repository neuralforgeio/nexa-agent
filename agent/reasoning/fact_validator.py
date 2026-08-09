"""
OpenForge — Fact Validator
============================

Validates factual claims in the agent's answer against web search
results. When a claim is found to be unsupported (or contradicted), the
validator flags it so the agent can re-issue the answer.

This is a thin orchestrator: the actual web search is injected so the
module is easily testable with a mock.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Pattern for extracting factual claims (sentences containing numbers/dates/years).
_CLAIM_PATTERN = re.compile(
    r"[A-Z][^.!?]*(?:\b\d{4}\b|\b\d[\d.,]*%?\b|\bUSD\b|\bUSD\s?\d+)[^.!?]*[.!?]"
)


@dataclass
class ValidationResult:
    """
    Result of validating a set of claims.

    Attributes:
        supported:    Claims that a source corroborates.
        unsupported:  Claims with no corroborating source.
        contradicted:Claims a source explicitly contradicts.
        sources_used: Number of sources consulted.
    """

    supported: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    contradicted: List[str] = field(default_factory=list)
    sources_used: int = 0

    @property
    def ok(self) -> bool:
        """Return ``True`` if no claim is contradicted or unsupported."""
        return not self.unsupported and not self.contradicted

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "supported": self.supported,
            "unsupported": self.unsupported,
            "contradicted": self.contradicted,
            "sources_used": self.sources_used,
            "ok": self.ok,
        }


def extract_claims(text: str, max_claims: int = 5) -> List[str]:
    """
    Extract factual claims from ``text``.

    A "claim" is a sentence containing numbers, dates, years, or
    monetary amounts — these are the most verifiable facts.

    Args:
        text:       The text to scan.
        max_claims: Maximum claims to return.

    Returns:
        A list of claim strings.
    """
    claims = _CLAIM_PATTERN.findall(text)
    # Deduplicate while preserving order.
    seen: set = set()
    unique: List[str] = []
    for c in claims:
        c_norm = c.strip()
        if c_norm not in seen:
            seen.add(c_norm)
            unique.append(c_norm)
    return unique[:max_claims]


async def validate_claims(
    claims: List[str],
    search_fn: Callable[[str], Any],
    max_per_claim: int = 1,
) -> ValidationResult:
    """
    Validate a list of claims against web search results.

    For each claim, runs a web search and checks whether the top
    result's snippet corroborates the claim's key number.

    Args:
        claims:       The claims to validate.
        search_fn:    Async callable ``async def (q) -> list[dict]``.
        max_per_claim:Max searches per claim (default 1).

    Returns:
        A :class:`ValidationResult`.
    """
    result = ValidationResult()
    for claim in claims:
        # Extract the key number from the claim.
        m = re.search(r"(\d[\d.,]*)", claim)
        if not m:
            # No verifiable number → skip (treat as supported by default).
            result.supported.append(claim)
            continue
        key_number = m.group(1).rstrip(".,")
        try:
            results = await search_fn(claim[:120])
        except Exception:
            result.unsupported.append(claim)
            continue
        result.sources_used += min(max_per_claim, len(results) if results else 0)
        if not results:
            result.unsupported.append(claim)
            continue
        # Check if the top snippet contains the same number.
        snippet = (
            results[0].get("snippet", "")
            or results[0].get("title", "")
        )
        if key_number in snippet:
            result.supported.append(claim)
        elif _is_contradicted(claim, snippet):
            result.contradicted.append(claim)
        else:
            result.unsupported.append(claim)
    return result


def _is_contradicted(claim: str, snippet: str) -> bool:
    """
    Heuristic: check if ``snippet`` looks like it contradicts ``claim``.

    Real contradiction detection is hard; this cheap heuristic only
    flags the most obvious case: the snippet's key number differs from
    the claim's and is on the same subject.
    """
    claim_num = re.search(r"(\d[\d.,]*)", claim)
    snip_num = re.search(r"(\d[\d.,]*)", snippet)
    if not (claim_num and snip_num):
        return False
    # Normalize: strip thousands separators.
    a = claim_num.group(1).replace(",", "").rstrip(".")
    b = snip_num.group(1).replace(",", "").rstrip(".")
    if a == b:
        return False
    # Same order of magnitude → likely a contradiction.
    try:
        if abs(int(float(a)) - int(float(b))) <= max(2, 0.1 * float(a)):
            return True
    except ValueError:
        return False
    return False
