"""
Nexa Agent — Web Search Tool
=============================

Provides the ``web_search`` tool for performing HTTP-based web searches.
Uses ``httpx`` for async HTTP requests with timeout and result capping.

The tool is designed to be provider-agnostic — it accepts a query string
and returns formatted search results. It does not depend on any specific
search API; instead, it uses DuckDuckGo's HTML endpoint as a free,
no-API-key-required search backend.

Design decisions:
    - **Async I/O**: Uses ``httpx.AsyncClient`` for non-blocking requests.
    - **No API key required**: Uses DuckDuckGo HTML scraping (free, public).
    - **Result capping**: Returns at most 5 results, each truncated to 200 chars.
    - **Timeout**: 10-second request timeout to prevent hanging.
    - **Graceful degradation**: Returns error message, never crashes.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
from typing import Any, Dict, List

import httpx


#: Maximum number of search results to return.
MAX_RESULTS: int = 5

#: Maximum snippet length per result (characters).
MAX_SNIPPET_LEN: int = 200

#: Request timeout in seconds.
REQUEST_TIMEOUT: float = 10.0

#: DuckDuckGo HTML search endpoint (no API key required).
SEARCH_URL: str = "https://html.duckduckgo.com/html/"


async def web_search(query: str, num_results: int = MAX_RESULTS, **_: Any) -> str:
    """
    Search the web for a query and return formatted results.

    Uses DuckDuckGo's HTML endpoint (free, no API key). Results are
    parsed from the HTML response and formatted as a text list.

    Args:
        query:       The search query string.
        num_results: Maximum number of results to return (default: 5, max: 10).

    Returns:
        A formatted string with search results, or an error message.

    Raises:
        ValueError: If the query is empty or whitespace-only.
    """
    if not query or not query.strip():
        raise ValueError("query is empty or whitespace-only")

    # Clamp num_results.
    num_results = max(1, min(num_results, 10))

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                SEARCH_URL,
                data={"q": query},
                headers={
                    "User-Agent": "NexaAgent/1.0 (Python web search tool)",
                },
            )
            response.raise_for_status()
            html = response.text

        results = _parse_ddg_html(html, num_results)
        if not results:
            return f"No results found for: {query}"

        lines = [f"Web search results for '{query}' ({len(results)} found):"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "(untitled)")[:100]
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:MAX_SNIPPET_LEN]
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   URL: {url}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")

        return "\n".join(lines)

    except httpx.TimeoutException:
        return f"Web search timed out after {REQUEST_TIMEOUT}s for query: {query}"
    except httpx.HTTPError as e:
        return f"Web search HTTP error: {e}"
    except Exception as e:
        return f"Web search failed: {e}"


def _parse_ddg_html(html: str, max_results: int) -> List[Dict[str, str]]:
    """
    Parse DuckDuckGo HTML search results.

    Extracts title, URL, and snippet from the HTML response using
    regex patterns. This is a best-effort parser — DuckDuckGo's HTML
    structure may change, so the parser is defensive.

    Args:
        html:        The raw HTML response from DuckDuckGo.
        max_results: Maximum number of results to extract.

    Returns:
        A list of dicts with 'title', 'url', and 'snippet' keys.
    """
    results: List[Dict[str, str]] = []

    # DuckDuckGo HTML uses result blocks with class="result__body".
    # Titles are in <a class="result__a" href="...">Title</a>.
    # Snippets are in <a class="result__snippet">Snippet text</a>.
    result_blocks = re.findall(
        r'<div class="result[^"]*">(.*?)</div>\s*(?=<div class="result|</div>\s*$)',
        html,
        re.DOTALL,
    )

    for block in result_blocks[:max_results]:
        result: Dict[str, str] = {}

        # Extract title and URL from the result link.
        title_match = re.search(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        if title_match:
            url = title_match.group(1)
            # DuckDuckGo wraps URLs in a redirect; extract the actual URL.
            url = re.search(r"uddg=([^&]+)", url)
            if url:
                from urllib.parse import unquote
                result["url"] = unquote(url.group(1))
            else:
                result["url"] = title_match.group(1)

            # Strip HTML tags from title.
            title = re.sub(r"<[^>]+>", "", title_match.group(2))
            result["title"] = title.strip()

        # Extract snippet.
        snippet_match = re.search(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        if snippet_match:
            snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1))
            result["snippet"] = snippet.strip()

        if result.get("title") or result.get("url"):
            results.append(result)

    return results


#: OpenAI function-calling schema for web_search.
WEB_SEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query string.",
        },
        "num_results": {
            "type": "number",
            "description": "Maximum results to return (default: 5, max: 10).",
        },
    },
    "required": ["query"],
}
