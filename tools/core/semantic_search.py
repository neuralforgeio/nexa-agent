"""semantic_search tool — retrieve the most relevant workspace chunks for a query.

Queries the workspace vector index (built by ``agent.workspace_indexer``)
and returns the top-k sources with a relevance score.
"""
from __future__ import annotations

from typing import Any

from nexa.embeddings import embed_text
from nexa.vector_db import VectorStore

SEMANTIC_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Natural-language search query."},
        "k":     {"type": "integer", "description": "Number of results (default 5).", "default": 5},
    },
    "required": ["query"],
}


async def semantic_search(query: str, k: int = 5, **_: Any) -> str:
    if not query.strip():
        raise ValueError("query is empty")
    store = VectorStore()
    store.initialize()
    results = store.search(embed_text(query), k=k)
    if not results:
        return "No workspace matches. Run the indexer first (agent.workspace_indexer)."
    lines = [f"Top {len(results)} workspace chunks for '{query}':"]
    for r in results:
        lines.append(f"[{r['score']:.3f}] {r['source']} (chunk {r['chunk_index']})")
        lines.append("  " + (r["content"][:240].replace("\n", " ")))
    return "\n".join(lines)
