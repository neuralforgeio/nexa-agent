"""
Nexa Agent — Planning Tools: Knowledge & State (v4.0.0)
========================================================

Three read-only tools that let the agent consult its own persistent
knowledge:

- :func:`memory_search`  — FTS5 search over long-term memories.
- :func:`session_search` — FTS5 search over past conversation messages.
- :func:`web_fetch`      — fetch a URL and extract human-readable text
  (lightweight, 32 KB cap, simple HTML boilerplate-strip).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import html
import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# memory_search
# ---------------------------------------------------------------------------
async def memory_search(query: str, kind: Optional[str] = None, limit: int = 8) -> str:
    """
    Search Nexa's long-term memory store (FTS5).

    Args:
        query: The search query.
        kind:  Optional memory kind filter (``insight``, ``preference``,
               ``fact``, ``skill``).
        limit: Max results (default 8, max 20).

    Returns:
        A Markdown list of matching memories with confidence and usage.
    """
    if not query.strip():
        return "**Error.** `query` cannot be empty."

    limit = max(1, min(limit, 20))
    # Lazy import so state.py stays optional at import time.
    from nexa.state import ConversationDB

    db = ConversationDB()
    await db.init()
    rows = await db.search_memories(query, limit=limit)

    if kind:
        rows = [r for r in rows if r.get("kind") == kind]

    if not rows:
        return f"No memories matching `{query}`."

    lines = [f"**{len(rows)} memory(ies) for `{query}`:**", ""]
    for r in rows:
        conf = r.get("confidence", 0.5)
        used = r.get("times_used", 0)
        content = (r.get("content") or "")[:220]
        lines.append(
            f"- **{r.get('kind', 'note')}** _{conf:.0%}, used {used}×_\n  {content}"
        )
    return "\n".join(lines)


MEMORY_SEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "kind": {"type": "string", "description": "insight|preference|fact|skill", "default": ""},
        "limit": {"type": "integer", "default": 8},
    },
    "required": ["query"],
}


# ---------------------------------------------------------------------------
# session_search
# ---------------------------------------------------------------------------
async def session_search(query: str, role: Optional[str] = None, limit: int = 8) -> str:
    """
    Search past conversation messages (FTS5).

    Args:
        query: The search query.
        role:  Optional role filter (``user``, ``assistant``, ``tool``).
        limit: Max results (default 8, max 20).

    Returns:
        Markdown list of matches with session ID and message preview.
    """
    if not query.strip():
        return "**Error.** `query` cannot be empty."

    limit = max(1, min(limit, 20))
    from nexa.state import ConversationDB

    db = ConversationDB()
    await db.init()
    rows = await db.search_messages(query, limit=limit)

    if role:
        rows = [r for r in rows if r.get("role") == role]

    if not rows:
        return f"No past messages matching `{query}`."

    lines = [f"**{len(rows)} message(s) for `{query}`:**", ""]
    for r in rows:
        content = (r.get("content") or "").replace("\n", " ")[:180]
        lines.append(
            f"- **[{r.get('role', '?')}]** in `{r.get('conversation_id', '?')}`"
            f" · {r.get('created_at', '')[:19]}\n  {content}…"
        )
    return "\n".join(lines)


SESSION_SEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "role": {"type": "string", "description": "user|assistant|tool", "default": ""},
        "limit": {"type": "integer", "default": 8},
    },
    "required": ["query"],
}


# ---------------------------------------------------------------------------
# web_fetch
# ---------------------------------------------------------------------------
_MAX_FETCH = 32 * 1024       # 32 KB decoded-text cap
_TIMEOUT_S = 12.0            # Reasonable for slow CDNs
_UA = "NexaAgent/4.0 (+https://github.com/neuralforgeio/nexa-agent)"


def _html_to_text(raw: str) -> str:
    """
    Very lightweight HTML → plain-text extractor.

    Strips scripts/styles/tags and decodes entities. Not a full browser
    engine, but enough to pull article text out of most pages.
    """
    raw = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    # Preserve block-level structure with newlines.
    raw = re.sub(r"(?is)</(p|div|section|article|h[1-6]|li|br)>", "\n", raw)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    # Collapse whitespace.
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


async def web_fetch(url: str, max_chars: int = 8192) -> str:
    """
    Fetch a URL and return its text content.

    Args:
        url:       The URL to fetch (http/https only).
        max_chars: Maximum characters of extracted text to return
                   (default 8192). The page is *fetched* up to 32 KB to
                   avoid memory bloat.

    Returns:
        The extracted text (Markdown-safe) with a title line, or an
        error string.
    """
    if not url.startswith(("http://", "https://")):
        return "**Error.** url must start with http:// or https://"

    # v4.1.0: replaced blocking urllib.request with httpx.AsyncClient so a
    # slow server doesn't freeze the asyncio event loop (and therefore every
    # other SSE stream running on it).
    import asyncio

    try:
        import httpx
    except ImportError:
        try:
            httpx = await asyncio.to_thread(
                lambda: __import__("httpx")
            )  # pragma: no cover
        except ImportError:
            return "**Error.** httpx not available."

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        ) as _client:
            resp = await _client.get(url)
            raw = resp.text[: _MAX_FETCH]
            ctype = resp.headers.get("content-type", "")
            final_url = str(resp.url)
    except Exception as exc:
        return f"**Fetch failed:** {exc}"

    # Only attempt HTML extraction for (likely) HTML; otherwise return raw.
    if "html" in ctype.lower() or raw.lstrip().lower().startswith(("<!doctype", "<html")):
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        title = title_match.group(1).strip() if title_match else "(no title)"
        body = _html_to_text(raw)
        prefix = f"# {title}\n\n*{final_url}*\n\n"
    else:
        prefix = f"# {final_url}\n\n_(raw {ctype or 'text'})_\n\n"
        body = raw

    body = body[: max(512, min(max_chars, 32_768))]
    if len(body) >= max_chars:
        body += "\n\n…[truncated]"
    return prefix + body


WEB_FETCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "http:// or https:// URL"},
        "max_chars": {"type": "integer", "default": 8192},
    },
    "required": ["url"],
}
