"""Watch the workspace, chunk changed files (500 tokens / 50 overlap), embed and store.

Drives RAG in Forge: any change under the workspace is re-chunked and embedded
into :class:`forge.vector_db.VectorStore` so ``semantic_search`` can find it.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from openforge.config import FORGE_WORKSPACE
from openforge.embeddings import embed_text
from openforge.vector_db import VectorStore

CHUNK_TOKENS = 500
OVERLAP = 50
WATCH_EXT = {".py", ".md", ".txt", ".json", ".js", ".ts", ".tsx", ".jsx"}


def _chunk(text: str, size: int = CHUNK_TOKENS, overlap: int = OVERLAP) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    out = []
    i = 0
    step = max(1, size - overlap)
    while i < len(words):
        out.append(" ".join(words[i : i + size]))
        i += step
    return out


class WorkspaceIndexer:
    def __init__(self) -> None:
        self.store = VectorStore()
        self.store.initialize()

    async def index_file(self, path: Path) -> int:
        if path.suffix.lower() not in WATCH_EXT or not path.is_file():
            return 0
        text = path.read_text("utf-8", errors="ignore")
        rel = str(path.relative_to(FORGE_WORKSPACE)).replace("\\", "/")
        self.store.delete_source(rel)
        chunks = _chunk(text)
        for i, c in enumerate(chunks):
            self.store.upsert(f"{rel}::{i}", rel, i, c, embed_text(c))
        return len(chunks)

    async def index_all(self) -> int:
        n = 0
        for p in FORGE_WORKSPACE.rglob("*"):
            if p.is_file() and p.suffix.lower() in WATCH_EXT:
                try:
                    n += await self.index_file(p)
                except Exception:
                    continue
        return n


async def main() -> None:  # manual entry point
    idx = WorkspaceIndexer()
    print(f"indexed chunks: {await idx.index_all()}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
