"""
OpenForge — deep_research skill (web_research)
================================================

Purpose
-------
Perform multi-source research on a topic at a caller-selected depth
(``quick`` | ``standard`` | ``deep``). Returns the manifest contract:
``summary`` (str), ``sources`` (array of ``{url, title, snippet,
credibility}``) and, when available, ``citations`` (array of str).

Permissions
-----------
Declared: ``network:*``, ``memory:read``, ``memory:write``.

Honesty note
------------
v0.1.0 has **no built-in search backend**: ``tool_api.http_client()`` can
fetch *explicit* URLs, but it cannot turn a bare ``topic`` string into a
list of sources on its own. This handler therefore attempts a network
fetch **only** when explicit URLs are supplied (an optional non-manifest
``sources``-style hint list, best-effort, short timeout). When no fetch is
possible — always the case in a hermetic test environment — the handler
relies on the provider model's *internal knowledge* and asks it to
synthesise what it knows about the topic. The ``summary`` always comes
from the model; the ``sources`` list is whatever the model itself supplied
(passed through after normalisation) or an empty list — never locally
invented URLs. LLM and JSON-parse errors propagate; they are never
swallowed or papered over with fabricated research.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent import tool_api
from skills._common import ask_llm_json, as_list, coerce_number, coerce_str, require

__all__ = ["handle", "SYSTEM"]

_FETCH_TIMEOUT = 5.0  # short, best-effort; hermetic tests fail fast

SYSTEM = (
    "You are the deep_research skill inside the Nexa Agent skills system. "
    "You are given a research topic, a depth (quick | standard | deep), and "
    "either real fetched page excerpts or (when no search backend / network "
    "is available) a note that you must rely on your internal knowledge only. "
    "Respond with a single JSON object and nothing else — no prose, no "
    "markdown fence. The object MUST have these keys:\n"
    '  "summary": string — the synthesis of what is known about the topic;\n'
    '  "sources": array of objects, each with keys "url", "title", "snippet", '
    '"credibility" (all strings; credibility is a short rating such as '
    '"high"/"medium"/"low"). ONLY include a source when its URL genuinely '
    "came from the fetched excerpts provided to you, or when you are certain "
    "of the canonical URL from your own knowledge. When in doubt or when "
    "there is no fetched material, return an EMPTY array — never invent "
    "plausible-looking URLs;\n"
    '  "citations": array of strings — short formatted citations for the '
    "sources you actually listed (may be empty)."
)


def _normalise_max_sources(input_data: Dict[str, Any]) -> int:
    value = input_data.get("max_sources", 10)
    try:
        n = int(coerce_number(value, default=10.0))
    except Exception:
        n = 10
    return max(1, n)


def _extract_url_hints(input_data: Dict[str, Any]) -> List[str]:
    """
    Collect explicit URL hints from the payload, if any.

    The manifest input schema is ``topic``/``depth``/``max_sources``; callers
    may *optionally* also pass explicit URLs (e.g. ``urls`` or
    ``source_urls``) — extra keys are ignored by schema validation but let a
    caller hand us fetch targets. When absent, no fetch is attempted.
    """
    hints: List[str] = []
    for key in ("urls", "source_urls", "seed_urls"):
        raw = input_data.get(key)
        for item in as_list(raw):
            s = coerce_str(item).strip()
            if s.startswith(("http://", "https://")):
                hints.append(s)
    return hints


async def _fetch_one(url: str) -> Optional[Dict[str, str]]:
    """Best-effort single fetch; None on any failure (never raises)."""
    try:
        client = tool_api.http_client(timeout=_FETCH_TIMEOUT)
        try:
            resp = await client.get(url)
            if getattr(resp, "status_code", 0) >= 400:
                return None
            text = coerce_str(getattr(resp, "text", ""))[:4000]
        finally:
            aclose = getattr(client, "aclose", None)
            if callable(aclose):
                res = aclose()
                if hasattr(res, "__await__"):
                    await res
    except Exception:
        return None  # honest degradation: offline, unroutable, junk -> skip
    return {"url": url, "excerpt": text} if text.strip() else None


async def _fetch_excerpts(urls: List[str], max_urls: int) -> List[Dict[str, str]]:
    """
    Best-effort fetch of explicit URLs. Offline-safe: any failure (no
    network, import error, connect refused, non-2xx) simply yields no
    excerpt for that URL — it is never fatal and never fabricates content.
    Fetches run concurrently so several slow hosts cost ~one timeout.
    """
    excerpts: List[Dict[str, str]] = []
    if not urls:
        return excerpts
    import asyncio

    results = await asyncio.gather(*(_fetch_one(u) for u in urls[:max_urls]))
    for r in results:
        if r is not None:
            excerpts.append(r)
    return excerpts


def _build_prompt(
    topic: str,
    depth: str,
    max_sources: int,
    excerpts: List[Dict[str, str]],
    had_url_hints: bool,
) -> str:
    lines = [
        f"Research topic: {topic}",
        f"Depth: {depth}",
        f"Maximum sources to list: {max_sources}",
        "",
    ]
    if excerpts:
        lines.append("Real fetched page excerpts (use these, and only these, "
                     "as your grounded sources):")
        for ex in excerpts:
            lines.append(f"- URL: {ex['url']}")
            lines.append(f"  Excerpt: {ex['excerpt']}")
    elif had_url_hints:
        lines.append(
            "NOTE: explicit URLs were supplied but every fetch failed "
            "(offline / unreachable host). Rely on your internal knowledge "
            "only and DO NOT list those URLs as sources unless you are "
            "certain they are canonical for the topic."
        )
    else:
        lines.append(
            "NOTE: no search backend and no network fetch are available in "
            "this run. Synthesise from your internal knowledge only. If you "
            "cannot name canonical source URLs with certainty, return an "
            "empty \"sources\" array — do not invent URLs."
        )
    return "\n".join(lines)


def _normalise_source(raw: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    url = coerce_str(raw.get("url")).strip()
    title = coerce_str(raw.get("title")).strip()
    if not url or not title:  # url+title are required by the output schema
        return None
    return {
        "url": url,
        "title": title,
        "snippet": coerce_str(raw.get("snippet")),
        "credibility": coerce_str(raw.get("credibility")),
    }


async def handle(input_data: dict, provider) -> dict:
    """
    Run the deep_research skill.

    Raises:
        SkillInputError: Missing/wrongly-typed ``topic`` or ``depth``.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    topic = require(input_data, "topic", str, "research topic")
    depth = require(input_data, "depth", str, "research depth")
    max_sources = _normalise_max_sources(input_data)

    url_hints = _extract_url_hints(input_data)
    excerpts = await _fetch_excerpts(url_hints, max_sources)

    prompt = _build_prompt(topic, depth, max_sources, excerpts, bool(url_hints))
    data = await ask_llm_json(provider, prompt, system=SYSTEM)

    sources: List[Dict[str, str]] = []
    for raw in as_list(data.get("sources")):
        src = _normalise_source(raw)
        if src is not None:
            sources.append(src)
        if len(sources) >= max_sources:
            break

    citations = [coerce_str(c) for c in as_list(data.get("citations"))]
    citations = [c for c in citations if c.strip()]

    return {
        # The summary always comes from the model; if the model omitted it,
        # the honest schema-valid default is an empty string — never a
        # locally fabricated synthesis.
        "summary": coerce_str(data.get("summary"), default=""),
        "sources": sources,
        "citations": citations,
    }
