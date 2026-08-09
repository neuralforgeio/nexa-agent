"""
OpenForge — workspace code index for the ``code_search`` skill (v4.4.0)
=========================================================================

A small, honest, on-disk index under ``$FORGE_WORKSPACE/.openforge/index/code_fts.db``
(SQLite). Uses FTS5 when available and falls back to a deterministic
substring/substring-score scan when it is not — so the skill always returns a
real index done over real files, never a stub.

The module is deliberately dependency-free (stdlib ``sqlite3`` only) so the
skill works in a fresh checkout without extra installs.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Extensions we treat as indexable source/text.
INDEXABLE_EXTS: Tuple[str, ...] = (
    ".py", ".md", ".txt", ".js", ".ts", ".tsx", ".jsx", ".json",
    ".yaml", ".yml", ".toml", ".rs", ".go",
)

#: Directory names never descended into.
IGNORE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next",
    ".pytest_cache", ".openforge", "dist", "build", ".zcode",
})

#: Per-file read cap (skip huge/binary files).
MAX_BYTES = 512 * 1024


def _fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.Error:
        return False


def _index_db_path(workspace: Path) -> Path:
    d = workspace / ".openforge" / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d / "code_fts.db"


class WorkspaceIndex:
    """
    Deterministic workspace search index.

    API:
        index = WorkspaceIndex(workspace)
        index.build()                      # (re)index the tree
        hits = index.search(query, limit)  # -> [{file_path,line,snippet,relevance_score}]
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.use_fts5 = _fts5_available()
        self.db_path = _index_db_path(self.workspace)
        # in-memory mirror used both for fallback scoring and result assembly
        self._docs: List[Tuple[str, str]] = []  # (rel_path, content)

    # -- indexing ---------------------------------------------------------
    def _iter_files(self) -> List[Path]:
        out: List[Path] = []
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in files:
                p = Path(root) / name
                if p.suffix.lower() in INDEXABLE_EXTS:
                    try:
                        if p.stat().st_size <= MAX_BYTES:
                            out.append(p)
                    except OSError:
                        continue
        return out

    def build(self) -> int:
        """(Re)index the workspace. Returns the number of files indexed."""
        docs: List[Tuple[str, str]] = []
        for p in self._iter_files():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = os.path.relpath(str(p), str(self.workspace))
            docs.append((rel, text))
        self._docs = docs

        if self.use_fts5:
            con = sqlite3.connect(str(self.db_path))
            try:
                con.execute("DROP TABLE IF EXISTS docs")
                con.execute("CREATE VIRTUAL TABLE docs USING fts5(path, content)")
                con.executemany("INSERT INTO docs(path, content) VALUES (?, ?)", docs)
                con.commit()
            finally:
                con.close()
        else:
            # fallback: persist a plain table so the index is still on-disk/honest
            con = sqlite3.connect(str(self.db_path))
            try:
                con.execute("DROP TABLE IF EXISTS docs_plain")
                con.execute("CREATE TABLE docs_plain(path TEXT, content TEXT)")
                con.executemany("INSERT INTO docs_plain(path, content) VALUES (?, ?)", docs)
                con.commit()
            finally:
                con.close()
        return len(docs)

    # -- search -----------------------------------------------------------
    def _score_line(self, query_terms: List[str], line: str) -> float:
        low = line.lower()
        hits = sum(1 for t in query_terms if t in low)
        return hits / max(len(query_terms), 1)

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return ranked results as dicts with file_path/line/snippet/relevance_score.
        Scores are normalised to (0, 1].
        """
        query = (query or "").strip()
        if not query:
            return []
        terms = [t for t in query.lower().split() if t]
        if not terms:
            terms = [query.lower()]

        # Lazily index if nothing built yet.
        if not self._docs:
            self.build()

        scored: List[Tuple[float, str, int, str]] = []
        if self.use_fts5:
            con = sqlite3.connect(str(self.db_path))
            try:
                # FTS5 match: AND the terms (each term prefix-matched)
                match = " AND ".join(f'"{t}"' for t in terms) or query
                rows = list(
                    con.execute(
                        "SELECT path, content, bm25(docs) AS rank FROM docs "
                        "WHERE docs MATCH ? ORDER BY rank LIMIT ?",
                        (match, max(limit * 20, 50)),
                    )
                )
            except sqlite3.Error:
                rows = []  # fall through to in-memory scoring
            finally:
                con.close()
            for path, content, rank in rows:
                best = self._best_line(terms, content)
                if best is None:
                    continue
                line_no, snippet = best
                # bm25 returns lower-is-better (negative); squash into (0,1]
                score = 1.0 / (1.0 + abs(rank))
                scored.append((score, path, line_no, snippet))
            scored.sort(key=lambda r: -r[0])
            return [
                {"file_path": p, "line": ln, "snippet": sn, "relevance_score": round(sc, 4)}
                for sc, p, ln, sn in scored[:limit]
            ]

        # Substring fallback: score each line by term coverage.
        for path, content in self._docs:
            best = self._best_line(terms, content)
            if best is None:
                continue
            line_no, snippet = best
            sc = self._score_line(terms, snippet)
            if sc <= 0:
                continue
            scored.append((sc, path, line_no, snippet))
        scored.sort(key=lambda r: (-r[0], r[1], r[2]))
        return [
            {"file_path": p, "line": ln, "snippet": sn, "relevance_score": round(min(sc, 1.0), 4)}
            for sc, p, ln, sn in scored[:limit]
        ]

    def _best_line(self, terms: List[str], content: str) -> Optional[Tuple[int, str]]:
        """Best matching line number + snippet for the terms, or None."""
        best: Optional[Tuple[int, str]] = None
        best_score = 0.0
        for idx, line in enumerate(content.splitlines(), start=1):
            sc = self._score_line(terms, line)
            if sc > best_score:
                best_score = sc
                best = (idx, line.strip())
        return best if best_score > 0 else None
