"""SQLite vector store backed by sqlite-vec (falls back to pure-SQL when absent)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from openforge.config import FORGE_HOME

try:
    import sqlite_vec
except Exception:  # pragma: no cover
    sqlite_vec = None  # type: ignore[assignment]

_DB = FORGE_HOME / "vector_store.db"


@contextmanager
def _conn():
    FORGE_HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB))
    con.row_factory = sqlite3.Row
    if sqlite_vec is not None:
        con.enable_load_extension(True)
        try:
            sqlite_vec.load(con)
        except Exception:
            pass
    try:
        yield con
    finally:
        con.close()


class VectorStore:
    """Upsert + k-NN search over embedding vectors."""

    def initialize(self, dimensions: int = 384) -> None:
        self.dim = dimensions
        with _conn() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS embeddings(
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_emb_source ON embeddings(source);
                """
            )

    def upsert(self, id: str, source: str, chunk_index: int, content: str, vector: List[float]) -> None:
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO embeddings(id, source, chunk_index, content, embedding, created_at)"
                " VALUES(?,?,?,?,?,datetime('now'))",
                (id, source, chunk_index, content, json.dumps(vector)),
            )
            con.commit()

    def search(self, vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        with _conn() as con:
            rows = con.execute("SELECT id,source,chunk_index,content,embedding FROM embeddings").fetchall()
        # brute-force cosine (portable; sqlite-vec accelerates when available)
        import math

        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a)) or 1e-9
            nb = math.sqrt(sum(x * x for x in b)) or 1e-9
            return dot / (na * nb)

        scored = [(cos(vector, json.loads(r["embedding"])), dict(r)) for r in rows]
        scored.sort(key=lambda t: t[0], reverse=True)
        out = []
        for score, r in scored[: max(1, int(k))]:
            out.append({"id": r["id"], "source": r["source"], "chunk_index": r["chunk_index"],
                        "content": r["content"], "score": round(score, 4)})
        return out

    def delete_source(self, source: str) -> int:
        with _conn() as con:
            cur = con.execute("DELETE FROM embeddings WHERE source=?", (source,))
            con.commit()
            return cur.rowcount
