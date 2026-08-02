"""
Nexa Agent — Session Search
===========================

Full-text search across conversation history using SQLite FTS5.
Original implementation.py`` session search logic —
original implementation.

This module provides :func:`search_sessions` which queries the FTS5 virtual
table to find conversations matching a free-text query. Results are ranked
by relevance and include message snippets.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import Any, Dict, List

from nexa.state import ConversationDB


async def search_sessions(db: ConversationDB, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search across all conversations using FTS5 full-text search.

    The query supports FTS5 syntax (prefix matching, boolean operators,
    phrase queries). Results are ranked by relevance and include:
        - conversation id, title, timestamps
        - matching message snippet
        - total match count per conversation

    Args:
        db:    The :class:`~nexa.state.ConversationDB` instance.
        query: The search query (FTS5 syntax, e.g. ``"python tool"``).
        limit: Maximum number of conversations to return.

    Returns:
        A list of result dicts sorted by relevance::

            [
                {
                    "conversation_id": "conv-abc123",
                    "title": "How to use Python tools",
                    "snippet": "...matching <mark>python tool</mark> call...",
                    "match_count": 3,
                    "created_at": "...",
                    "updated_at": "...",
                },
                ...
            ]

    Example::

        results = await search_sessions(db, "file write")
        for r in results:
            print(f"{r['title']}: {r['snippet']}")
    """
    if not query.strip():
        return []

    # Use FTS5 to find matching messages, grouped by conversation.
    import aiosqlite
    from nexa.config import NEXA_DB_PATH

    async with aiosqlite.connect(str(NEXA_DB_PATH)) as conn:
        conn.row_factory = aiosqlite.Row

        # Step 1: Find matching messages grouped by conversation (no snippet).
        cursor = await conn.execute(
            """
            SELECT
                m.conversation_id,
                c.title,
                c.created_at,
                c.updated_at,
                COUNT(*) as match_count
            FROM messages_fts f
            JOIN messages m ON m.rowid = f.rowid
            JOIN conversations c ON c.id = m.conversation_id
            WHERE messages_fts MATCH ?
            GROUP BY m.conversation_id
            ORDER BY match_count DESC, c.updated_at DESC
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()

        # Step 2: For each conversation, get one snippet from a matching message.
        results: List[Dict[str, Any]] = []
        for row in rows:
            conv_id = row["conversation_id"]
            # Get a snippet from the first matching message in this conversation.
            snip_cursor = await conn.execute(
                """
                SELECT snippet(messages_fts, 0, '<<', '>>', '...', 20) as snip
                FROM messages_fts f
                JOIN messages m ON m.rowid = f.rowid
                WHERE m.conversation_id = ? AND messages_fts MATCH ?
                LIMIT 1
                """,
                (conv_id, query),
            )
            snip_row = await snip_cursor.fetchone()
            snippet_text = snip_row["snip"] if snip_row else ""

            results.append(
                {
                    "conversation_id": conv_id,
                    "title": row["title"],
                    "snippet": snippet_text,
                    "match_count": row["match_count"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

    return results


def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """
    Format search results as a human-readable string for TUI display.

    Args:
        results: The list of result dicts from :func:`search_sessions`.
        query:   The original query string (for the header).

    Returns:
        A formatted multi-line string.
    """
    if not results:
        return f"No results for '{query}'."

    lines = [f"🔍 Search results for '{query}' ({len(results)} conversations):", ""]
    for i, r in enumerate(results, 1):
        # Replace FTS5 snippet markers with readable highlights.
        snippet = r["snippet"].replace("<<", "\033[33m").replace(">>", "\033[0m")
        lines.append(
            f"  {i}. [{r['title'][:50]}] "
            f"({r['match_count']} match{'es' if r['match_count'] != 1 else ''})"
        )
        lines.append(f"     {snippet[:120]}")
        lines.append(f"     [dim]{r['conversation_id']}[/dim]")
        lines.append("")
    return "\n".join(lines)
