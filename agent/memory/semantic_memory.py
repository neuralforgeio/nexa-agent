"""
Nexa Agent — Semantic Vector Memory (v4.1.0)
=============================================

A lightweight semantic memory store that retrieves past memories/conversations
by *meaning*, not just keyword match. Uses TF-IDF + cosine similarity (pure
Python, no external dependencies like ChromaDB or FAISS).

Why TF-IDF instead of embeddings?
    - Zero extra dependencies (works in any Python environment).
    - Fast for small-to-medium corpora (< 10k documents).
    - Good enough for "find similar past conversations" recall.
    - Embeddings (ChromaDB/FAISS) can be added as an optional backend later
      (see ROADMAP_20_FEATURES.md feature 1.1).

Storage:
    - Documents (memories + past messages) are stored as JSONL in
      ``~/.openforge/memory/semantic.jsonl``.
    - The TF-IDF index is built in-memory on load + updated on add.

Usage:
    >>> from agent.memory.semantic_memory import SemanticMemory
    >>> sm = SemanticMemory()
    >>> sm.add("user_prefers_python", "The user prefers Python over JavaScript")
    >>> results = sm.search("what language does the user like?")
    >>> results[0]["doc_id"]
    'user_prefers_python'

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openforge.config import FORGE_HOME


#: Default storage path.
DEFAULT_SEMANTIC_PATH: Path = FORGE_HOME / "memory" / "semantic.jsonl"

#: Stopwords for TF-IDF tokenization (English + common code tokens).
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "can", "to", "of",
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "from",
    "up", "down", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s",
    "t", "just", "i", "you", "he", "she", "it", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "its", "our", "their", "this",
    "that", "these", "those", "what", "which", "who", "whom",
})

#: Max results returned by search().
DEFAULT_TOP_K: int = 5

#: Minimum similarity score to include in results.
MIN_SIMILARITY: float = 0.05


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into lowercase words (stopwords removed).

    Args:
        text: The input text.

    Returns:
        A list of tokens.

    Example:
        >>> _tokenize("The user prefers Python!")
        ['user', 'prefers', 'python']
    """
    # Split on non-alphanumeric, lowercase, filter stopwords + short tokens.
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


@dataclass
class SemanticDocument:
    """
    A document in the semantic memory store.

    Attributes:
        doc_id:    Unique identifier (e.g. "mem-1", "conv-123-turn-4").
        content:   The text content.
        kind:      Document type ("memory", "conversation", "fact", etc.).
        metadata:  Optional metadata (timestamps, session IDs, etc.).
    """

    doc_id: str
    content: str
    kind: str = "memory"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe).

        The ``id`` key is present for consumers that expect a generic document
        shape (``doc_id`` is the canonical key; ``id`` is an alias for the same
        value so callers don't need to know which attribute to use).
        """
        return {
            "doc_id": self.doc_id,
            "id": self.doc_id,  # alias for generic doc consumers
            "content": self.content,
            "kind": self.kind,
            "metadata": self.metadata,
        }


class SemanticMemory:
    """
    TF-IDF + cosine similarity semantic memory store.

    Documents are persisted to ``~/.openforge/memory/semantic.jsonl`` (append-only).
    The TF-IDF index is rebuilt in-memory on load.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """
        Initialize the semantic memory store.

        Args:
            path: Override for the storage path (default FORGE_HOME/memory/semantic.jsonl).
        """
        self.path: Path = path or DEFAULT_SEMANTIC_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._docs: Dict[str, SemanticDocument] = {}
        self._tokens: Dict[str, List[str]] = {}  # doc_id → tokens
        self._df: Dict[str, int] = {}  # term → document frequency
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load documents from the JSONL file + rebuild the TF-IDF index."""
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                doc = SemanticDocument(
                    doc_id=d["doc_id"],
                    content=d["content"],
                    kind=d.get("kind", "memory"),
                    metadata=d.get("metadata", {}),
                )
                self._docs[doc.doc_id] = doc
                tokens = _tokenize(doc.content)
                self._tokens[doc.doc_id] = tokens
                # Update document frequency.
                for term in set(tokens):
                    self._df[term] = self._df.get(term, 0) + 1
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    def _append(self, doc: SemanticDocument) -> None:
        """Append a document to the JSONL file."""
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add(self, doc_id: str, content: str, kind: str = "memory",
            metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add or update a document.

        Args:
            doc_id:   Unique identifier.
            content:  The text content.
            kind:     Document type.
            metadata: Optional metadata.

        Example:
            >>> sm = SemanticMemory()
            >>> sm.add("mem-1", "The user prefers Python")
        """
        doc = SemanticDocument(
            doc_id=doc_id, content=content, kind=kind,
            metadata=metadata or {},
        )
        # If the doc already exists, remove its old DF contributions first.
        if doc_id in self._docs:
            old_tokens = self._tokens.get(doc_id, [])
            for term in set(old_tokens):
                if term in self._df:
                    self._df[term] -= 1
                    if self._df[term] <= 0:
                        del self._df[term]
        # Store + index.
        self._docs[doc_id] = doc
        tokens = _tokenize(content)
        self._tokens[doc_id] = tokens
        for term in set(tokens):
            self._df[term] = self._df.get(term, 0) + 1
        # Persist (append; the file may have duplicates if updating — that's OK,
        # the in-memory index is authoritative).
        self._append(doc)

    def get(self, doc_id: str) -> Optional[SemanticDocument]:
        """Return the document ``doc_id`` (or ``None``)."""
        return self._docs.get(doc_id)

    def remove(self, doc_id: str) -> bool:
        """
        Remove a document from the in-memory index.

        Note: this does NOT rewrite the JSONL file (append-only). The document
        will reappear on next load unless ``save_all()`` is called.

        Args:
            doc_id: The document ID to remove.

        Returns:
            ``True`` if removed, ``False`` if not found.
        """
        if doc_id not in self._docs:
            return False
        tokens = self._tokens.get(doc_id, [])
        for term in set(tokens):
            if term in self._df:
                self._df[term] -= 1
                if self._df[term] <= 0:
                    del self._df[term]
        del self._docs[doc_id]
        del self._tokens[doc_id]
        return True

    def list_all(self) -> List[SemanticDocument]:
        """Return all documents."""
        return list(self._docs.values())

    def count(self) -> int:
        """Return the number of documents."""
        return len(self._docs)

    def save_all(self) -> None:
        """Rewrite the JSONL file from the in-memory index (compact)."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                for doc in self._docs.values():
                    f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def clear(self) -> int:
        """
        Delete all documents + the JSONL file.

        Returns:
            The number of documents deleted.
        """
        n = len(self._docs)
        self._docs.clear()
        self._tokens.clear()
        self._df.clear()
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass
        return n

    # ------------------------------------------------------------------
    # Search (TF-IDF + cosine similarity)
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = MIN_SIMILARITY,
        kind_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for documents semantically similar to ``query``.

        Args:
            query:          The search query.
            top_k:          Max results to return.
            min_similarity: Minimum cosine similarity to include.
            kind_filter:    Optional filter by document kind.

        Returns:
            A list of ``{doc_id, content, kind, metadata, score}`` dicts,
            sorted by score (descending).

        Example:
            >>> sm = SemanticMemory()
            >>> sm.add("m1", "I love Python programming")
            >>> sm.add("m2", "The weather is nice today")
            >>> results = sm.search("what language do you like?")
            >>> results[0]["doc_id"]
            'm1'
        """
        query_tokens = _tokenize(query)
        if not query_tokens or not self._docs:
            return []
        n_docs = len(self._docs)
        # Compute query TF-IDF vector.
        query_tf: Dict[str, int] = {}
        for t in query_tokens:
            query_tf[t] = query_tf.get(t, 0) + 1
        query_vec: Dict[str, float] = {}
        for term, tf in query_tf.items():
            df = self._df.get(term, 0)
            if df == 0:
                continue  # term not in any doc
            idf = math.log((n_docs + 1) / (df + 1)) + 1  # smoothed idf
            query_vec[term] = tf * idf
        if not query_vec:
            return []
        query_norm = math.sqrt(sum(v * v for v in query_vec.values()))

        # Score each document.
        scores: List[Tuple[str, float]] = []
        for doc_id, doc in self._docs.items():
            if kind_filter and doc.kind != kind_filter:
                continue
            doc_tokens = self._tokens.get(doc_id, [])
            if not doc_tokens:
                continue
            # Doc TF-IDF vector (only terms in query_vec matter for cosine).
            doc_tf: Dict[str, int] = {}
            for t in doc_tokens:
                if t in query_vec:
                    doc_tf[t] = doc_tf.get(t, 0) + 1
            if not doc_tf:
                continue
            n_doc_terms = len(doc_tokens)
            doc_vec: Dict[str, float] = {}
            for term, tf in doc_tf.items():
                df = self._df.get(term, 0)
                idf = math.log((n_docs + 1) / (df + 1)) + 1
                doc_vec[term] = (tf / n_doc_terms) * idf
            # Cosine similarity (only over shared terms).
            dot = sum(query_vec.get(t, 0.0) * doc_vec.get(t, 0.0) for t in query_vec)
            doc_norm = math.sqrt(sum(v * v for v in doc_vec.values()))
            if query_norm == 0 or doc_norm == 0:
                continue
            similarity = dot / (query_norm * doc_norm)
            if similarity >= min_similarity:
                scores.append((doc_id, similarity))

        # Sort by score descending, take top_k.
        scores.sort(key=lambda x: x[1], reverse=True)
        results: List[Dict[str, Any]] = []
        for doc_id, score in scores[:top_k]:
            doc = self._docs[doc_id]
            results.append({
                "doc_id": doc_id,
                "content": doc.content,
                "kind": doc.kind,
                "metadata": doc.metadata,
                "score": round(score, 4),
            })
        return results


def is_semantic_memory_enabled() -> bool:
    """Return True if semantic memory is enabled via env (NEXA_SEMANTIC_MEMORY=1)."""
    return os.environ.get("NEXA_SEMANTIC_MEMORY", "1").lower() in ("1", "true", "yes")
