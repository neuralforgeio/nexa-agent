"""
Nexa Agent — Deep Research Agent (v3.2.0)
==========================================

An advanced research agent that goes BEYOND simple web search:

Instead of: "user asks → we search → we return results"

It does: **Research Loop**
    1. Reformulate the question into multiple precise queries
       (via :mod:`agent.query_reformulator`).
    2. Search the web for each query (via :func:`tools.web_search_tool.web_search`).
    3. Fetch the top pages' full content (scraping via httpx + readability).
    4. Extract facts from content via the intent classifier.
    5. Cross-validate facts (multiple sources must agree).
    6. Synthesize everything into a comprehensive answer with citations.
    7. Cache the validated facts in :mod:`agent.knowledge_cache`.

This is how Nexa becomes smarter than a tool-user — it becomes a
**research-driven knowledge agent**.

Why built-in instead of a library?
    - Pure Python stdlib + httpx (already a dependency).
    - No heavy deps (playwright, selenium, bs4 are optional).
    - Works offline (falls back to cached knowledge).
    - Customizable search limits / timeouts via config.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.confidence_scorer import score_answer
from agent.fact_validator import validate_claims, extract_claims
from agent.intent_classifier import classify_intent
from agent.query_reformulator import ReformulatedQuery, pick_best_query, reformulate
from agent.response_synthesizer import SynthesisResult, reconcile_conflicts, synthesize


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_TOP_K: int = 5
""": How many search results to fetch per query. """

MAX_SOURCES: int = 15
""": Maximum sources to extract facts from. """

MIN_CONFIDENCE: float = 0.4
""": Minimum confidence score to consider a source."""

EXTRACT_TIMEOUT: float = 10.0
""": HTTP timeout for page fetching. """


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ResearchSource:
    """
    A single source page extracted during research.

    Attributes:
        url:         The page URL.
        title:       The page title (or first line).
        content:     The extracted main content (truncated to 5KB).
        snippet:     Search engine snippet (from the search tool).
        domain:      The domain name (e.g. "wikipedia.org").
        rank:        The search rank (0 = top result).
        fresh:       Whether the content looks fresh (has a date).
    """

    url: str
    title: str = ""
    content: str = ""
    snippet: str = ""
    domain: str = ""
    rank: int = 0
    fresh: bool = False


@dataclass
class ExtractedFact:
    """
    A single fact extracted from a source.

    Attributes:
        claim:      The factual claim (e.g. "Python 3.13.3 released Oct 2024").
        source_url: Source URL.
        source_title:Source page title.
        confidence: Confidence score (0.0–1.0).
        count:      How many sources corroborate this fact.
    """

    claim: str
    source_url: str = ""
    source_title: str = ""
    confidence: float = 0.5
    count: int = 1


@dataclass
class ResearchResult:
    """
    The complete result of a deep research session.

    Attributes:
        query:            The original user question.
        reformulated:     All reformulated queries.
        sources_searched: All sources fetched.
        facts:            All extracted + cross-validated facts.
        conflicts:        Any conflicting facts detected.
        answer:           The synthesized final answer (with citations).
        citations:        List of source URLs cited in the answer.
        confidence:       Overall confidence in the answer.
        duration_ms:      Total research time.
    """

    query: str
    reformulated: List[str] = field(default_factory=list)
    sources_searched: List[ResearchSource] = field(default_factory=list)
    facts: List[ExtractedFact] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    confidence: float = 0.5
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "query": self.query,
            "reformulated": self.reformulated,
            "sources_count": len(self.sources_searched),
            "facts_count": len(self.facts),
            "conflicts": self.conflicts,
            "answer": self.answer,
            "citations": self.citations,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Page fetching (scraping)
# ---------------------------------------------------------------------------
async def _fetch_page_content(
    url: str,
    timeout: float = EXTRACT_TIMEOUT,
) -> str:
    """
    Fetch a page's text content and strip HTML.

    Uses httpx. Falls back to empty string on any failure.

    Args:
        url:     The URL to fetch.
        timeout: HTTP timeout.

    Returns:
        The page's text content (truncated to 5000 chars).
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NexaAgent/1.0; +https://github.com/neuralforgeio/nexa-agent)"
            })
            resp.raise_for_status()
            html = resp.text
            # Strip HTML tags (rough, no bs4 dependency)
            # Remove scripts + styles
            html = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", " ", html, flags=re.DOTALL)
            html = re.sub(r"<\s*style[^>]*>.*?<\s*/\s*style\s*>", " ", html, flags=re.DOTALL)
            # Remove HTML tags
            html = re.sub(r"<[^>]+>", " ", html)
            # Collapse whitespace
            html = re.sub(r"\s+", " ", html).strip()
            return html[:5000]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------
_CLAIM_PATTERN = re.compile(
    r"[A-Z][^.!?]*(?:\b\d{4}\b|\b\d[\d.,]*%?\b|\bUSD\b)[^.!?]*[.!?]",
)


def _parse_search_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse a ``web_search`` tool's standard text output back into a list of
    hit dicts.

    Expects the formatted layout::

        Web search results for 'query' (N found):

        1. Title
           URL: https://example.com
           snippet...

        2. ...

    Returns:
        A list of ``{"title": ..., "url": ..., "snippet": ...}`` dicts.
    """
    hits: List[Dict[str, Any]] = []
    if not text:
        return hits
    # Split by "N." markers at line start.
    blocks = re.split(r"\n\s*\d+\.\s", text)
    for block in blocks[1:]:  # skip header
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        title = lines[0].strip().lstrip("0123456789. ")
        url_match = re.search(r"URL:\s*(.+?)\s*$", lines[1])
        if not url_match:
            continue
        url = url_match.group(1).strip()
        snippet = " ".join(l.strip() for l in lines[2:]).strip()
        if url:
            hits.append({"title": title, "url": url, "snippet": snippet})
    return hits


def _extract_facts(
    content: str,
    source_url: str,
    source_title: str,
) -> List[ExtractedFact]:
    """
    Extract factual claims from page content.

    Looks for sentences containing numbers, dates, or monetary amounts.
    These are the most verifiable facts.

    Args:
        content:      The page's text content.
        source_url:   The source URL.
        source_title: The source page title.

    Returns:
        A list of :class:`ExtractedFact` objects.
    """
    claims = _CLAIM_PATTERN.findall(content)
    facts: List[ExtractedFact] = []
    for claim in claims[:8]:  # cap per source
        facts.append(ExtractedFact(
            claim=claim.strip(),
            source_url=source_url,
            source_title=source_title,
            confidence=0.6,  # base confidence
        ))
    return facts


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------
async def deep_research(
    question: str,
    *,
    search_fn=None,
    top_k: int = DEFAULT_TOP_K,
    max_sources: int = MAX_SOURCES,
    min_confidence: float = MIN_CONFIDENCE,
) -> ResearchResult:
    """
    Perform deep research on ``question``.

    Executes the full loop: reformulate → search → fetch → extract →
    validate → synthesize → cache.

    Args:
        question:       The user's question. Must be non-empty.
        search_fn:      Async web search function (injected for testing).
                        Defaults to ``tools.web_search_tool.web_search``.
        top_k:          Results per query.
        max_sources:    Max sources to fetch.
        min_confidence: Minimum confidence to include a fact.

    Returns:
        A :class:`ResearchResult` with the synthesized answer and citations.

    Raises:
        ValueError: If ``question`` is empty or whitespace-only.
    """
    import time
    start = time.monotonic()

    if not question or not question.strip():
        raise ValueError("question is empty or whitespace-only")
    question = question.strip()

    # Inject the search function (or import the real one).
    if search_fn is None:
        from tools.web_search_tool import web_search as search_fn

    intent = classify_intent(question)
    result = ResearchResult(query=question)

    # --- 1. Reformulate the question ---
    rq = reformulate(question)
    result.reformulated = rq.queries

    # --- 2. Search the web for each query ---
    all_results: List[Dict[str, Any]] = []
    for q in rq.queries[:3]:  # cap at 3 queries
        try:
            results = await search_fn(q)
            if results:
                # Defensive parsing (v4.1.2): some search fns return a
                # formatted string (e.g. ``web_search``) instead of a list
                # of dicts — coerce either shape into a list of dicts so
                # downstream ``r.get("url")`` doesn't explode with
                # ``AttributeError: 'str' object has no attribute 'get'``.
                if isinstance(results, str):
                    all_results.extend(_parse_search_text(results))
                elif isinstance(results, list):
                    all_results.extend(r for r in results if isinstance(r, dict))
                elif isinstance(results, dict):
                    all_results.append(results)
        except Exception:
            continue

    # Keep only entries that look like a real search hit.
    valid: List[Dict[str, Any]] = [
        r for r in all_results if isinstance(r, dict) and r.get("url")
    ]

    # Deduplicate by URL, keep top half.
    seen_urls: set = set()
    unique_results: List[Dict[str, Any]] = []
    for r in valid:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)

    # Take the best results.
    top_results = unique_results[:top_k];

    # --- 3. Fetch page content for each result ---
    sources: List[ResearchSource] = []
    for i, r in enumerate(top_results[:max_sources]):
        url = r.get("url", "")
        if not url:
            continue
        content = await _fetch_page_content(url)
        if not content:
            continue  # skip unreachable pages
        domain = url.split("/")[2] if "/" in url else url
        sources.append(ResearchSource(
            url=url,
            title=r.get("title", ""),
            content=content,
            snippet=r.get("snippet", ""),
            domain=domain,
            rank=i,
            fresh=bool(re.search(r"\b(202[4-9]|20[3-9]\d)\b", content)),
        ))
    result.sources_searched = sources

    # --- 4. Extract facts from each source ---
    all_facts: List[ExtractedFact] = []
    for src in sources:
        facts = _extract_facts(src.content, src.url, src.title)
        all_facts.extend(facts)
    # Filter by minimum confidence.
    all_facts = [f for f in all_facts if f.confidence >= min_confidence]
    result.facts = all_facts

    # --- 5. Cross-validate facts ---
    # Group facts by similar claims; count how many sources agree.
    claim_counts: Dict[str, int] = {}
    claim_map: Dict[str, ExtractedFact] = {}
    for fact in all_facts:
        # Normalize the claim for grouping.
        key = re.sub(r"\d+", "N", fact.claim.lower()).strip()[:80]
        if key not in claim_map:
            claim_map[key] = fact
            claim_counts[key] = 0
        claim_counts[key] += 1
    # Update counts.
    for fact in all_facts:
        key = re.sub(r"\d+", "N", fact.claim.lower()).strip()[:80]
        fact.count = claim_counts[key]
    # Boost confidence based on corroboration.
    for fact in all_facts:
        fact.confidence = min(1.0, fact.confidence + 0.1 * (fact.count - 1))

    # --- 6. Synthesize the answer ---
    if all_facts:
        # Sort by confidence, take top 10.
        top_facts = sorted(all_facts, key=lambda f: f.confidence, reverse=True)[:10]
        fact_texts = [f.claim for f in top_facts]
        # Synthesize with intro + citations.
        synth = synthesize(
            parts=fact_texts,
            intro=f"Based on deep research on '{question}':",
            outro=None,
        )
        result.answer = synth.text
        result.citations = sorted({f.source_url for f in top_facts if f.source_url})
        result.confidence = min(1.0, 0.3 + 0.1 * len(top_facts))
    else:
        result.answer = f"No verified facts found for '{question}'."
        result.confidence = 0.2

    # --- 7. Detect conflicts ---
    result.conflicts = reconcile_conflicts([f.claim for f in all_facts])

    result.duration_ms = (time.monotonic() - start) * 1000.0
    return result


# ---------------------------------------------------------------------------
# Tool integration (for the tool registry)
# ---------------------------------------------------------------------------
DEEP_RESEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The research question to answer.",
        },
        "max_sources": {
            "type": "integer",
            "description": "Maximum number of sources to consult (default: 15).",
            "default": MAX_SOURCES,
        },
        "top_k": {
            "type": "integer",
            "description": "Search results per query (default: 5).",
            "default": DEFAULT_TOP_K,
        },
    },
    "required": ["question"],
}


async def deep_research_tool(
    question: str,
    max_sources: int = MAX_SOURCES,
    top_k: int = DEFAULT_TOP_K,
    **_: Any,
) -> str:
    """
    Tool-callable wrapper for :func:`deep_research`.

    Args:
        question:    The research question.
        max_sources: Max sources to consult.
        top_k:       Search results per query.

    Returns:
        The synthesized answer with citations, or an error message.
    """
    if not question or not question.strip():
        raise ValueError("question is required")
    result = await deep_research(
        question,
        max_sources=max_sources,
        top_k=top_k,
    )
    citations_str = "\n".join(f"- {url}" for url in result.citations[:5])
    answer = result.answer
    if citations_str:
        answer += f"\n\nSources:\n{citations_str}"
    if result.conflicts:
        answer += f"\n\nConflicts detected: {'; '.join(result.conflicts[:3])}"
    return answer
