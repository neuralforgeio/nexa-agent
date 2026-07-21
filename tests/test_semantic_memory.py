"""
Tests for the Semantic Vector Memory (v3.1.0).

Verifies:
    - SemanticMemory.add/get/remove/list_all/count.
    - search returns semantically similar documents (TF-IDF cosine).
    - search respects top_k and min_similarity.
    - search respects kind_filter.
    - Persistence (JSONL round-trip).
    - clear() deletes everything.
    - Tokenization removes stopwords.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path

import pytest

from agent.semantic_memory import (
    DEFAULT_SEMANTIC_PATH,
    SemanticDocument,
    SemanticMemory,
    _tokenize,
    is_semantic_memory_enabled,
)


class TestTokenize:
    """Tests for the tokenizer."""

    def test_removes_stopwords(self) -> None:
        """Stopwords are removed."""
        tokens = _tokenize("the quick brown fox jumps over the lazy dog")
        assert "the" not in tokens
        assert "over" not in tokens
        assert "quick" in tokens
        assert "fox" in tokens

    def test_lowercases(self) -> None:
        """Tokens are lowercased."""
        tokens = _tokenize("Python Is Great")
        assert "python" in tokens
        assert "is" not in tokens  # stopword
        assert "great" in tokens

    def test_handles_code_tokens(self) -> None:
        """Code identifiers are tokenized."""
        tokens = _tokenize("read_file write_file run_terminal_command")
        assert "read_file" in tokens
        assert "write_file" in tokens

    def test_empty_string(self) -> None:
        """Empty input produces empty tokens."""
        assert _tokenize("") == []

    def test_punctuation_only(self) -> None:
        """Punctuation-only input produces empty tokens."""
        assert _tokenize("!!! ??? ...") == []


class TestSemanticMemoryCRUD:
    """Tests for add/get/remove/list/count."""

    def test_add_and_get(self, tmp_path: Path) -> None:
        """add + get round-trip works."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "The user prefers Python")
        doc = sm.get("m1")
        assert doc is not None
        assert doc.content == "The user prefers Python"
        assert doc.kind == "memory"

    def test_get_unknown_returns_none(self, tmp_path: Path) -> None:
        """get() returns None for an unknown doc_id."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        assert sm.get("nonexistent") is None

    def test_list_all(self, tmp_path: Path) -> None:
        """list_all returns all documents."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "doc one")
        sm.add("m2", "doc two")
        all_docs = sm.list_all()
        assert len(all_docs) == 2

    def test_count(self, tmp_path: Path) -> None:
        """count returns the number of documents."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        assert sm.count() == 0
        sm.add("m1", "doc one")
        assert sm.count() == 1
        sm.add("m2", "doc two")
        assert sm.count() == 2

    def test_remove(self, tmp_path: Path) -> None:
        """remove deletes a document."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "doc one")
        assert sm.remove("m1") is True
        assert sm.get("m1") is None
        assert sm.count() == 0

    def test_remove_unknown_returns_false(self, tmp_path: Path) -> None:
        """remove returns False for an unknown doc_id."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        assert sm.remove("nonexistent") is False

    def test_update_existing(self, tmp_path: Path) -> None:
        """add with an existing doc_id updates the document."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "original content")
        sm.add("m1", "updated content")
        doc = sm.get("m1")
        assert doc.content == "updated content"
        assert sm.count() == 1  # not duplicated


class TestSemanticMemorySearch:
    """Tests for the TF-IDF cosine similarity search."""

    def test_search_returns_similar(self, tmp_path: Path) -> None:
        """search returns documents semantically similar to the query."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "The user prefers Python programming language")
        sm.add("m2", "Today's weather is sunny and warm")
        results = sm.search("what programming language does the user like?")
        assert len(results) > 0
        assert results[0]["doc_id"] == "m1"
        assert results[0]["score"] > 0

    def test_search_respects_top_k(self, tmp_path: Path) -> None:
        """search respects the top_k limit."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        for i in range(10):
            sm.add(f"m{i}", f"document number {i} about Python programming")
        results = sm.search("Python programming", top_k=3)
        assert len(results) <= 3

    def test_search_min_similarity(self, tmp_path: Path) -> None:
        """search filters out low-similarity results."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "Python programming")
        sm.add("m2", "cooking pasta recipes")
        # "Python programming" matches the query; "cooking pasta" doesn't.
        results = sm.search("Python code", min_similarity=0.5)
        doc_ids = [r["doc_id"] for r in results]
        assert "m1" in doc_ids
        assert "m2" not in doc_ids

    def test_search_kind_filter(self, tmp_path: Path) -> None:
        """search respects the kind_filter."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "Python programming", kind="memory")
        sm.add("m2", "Python programming", kind="conversation")
        results = sm.search("Python", kind_filter="memory")
        assert all(r["kind"] == "memory" for r in results)
        assert any(r["doc_id"] == "m1" for r in results)

    def test_search_empty_store(self, tmp_path: Path) -> None:
        """search on an empty store returns []."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        assert sm.search("anything") == []

    def test_search_no_query_tokens(self, tmp_path: Path) -> None:
        """search with only stopwords returns []."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "Python programming")
        assert sm.search("the a an") == []

    def test_search_returns_score(self, tmp_path: Path) -> None:
        """search results include a 'score' field."""
        sm = SemanticMemory(path=tmp_path / "sem.jsonl")
        sm.add("m1", "Python programming is fun")
        results = sm.search("Python programming")
        assert "score" in results[0]
        assert 0.0 <= results[0]["score"] <= 1.0


class TestSemanticMemoryPersistence:
    """Tests for JSONL persistence."""

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        """Documents survive a new SemanticMemory instance (reload from file)."""
        path = tmp_path / "sem.jsonl"
        sm1 = SemanticMemory(path=path)
        sm1.add("m1", "The user prefers Python")
        sm1.add("m2", "Today is sunny")
        # Create a new instance — should load from file.
        sm2 = SemanticMemory(path=path)
        assert sm2.count() == 2
        doc = sm2.get("m1")
        assert doc is not None
        assert "Python" in doc.content

    def test_save_all_compacts(self, tmp_path: Path) -> None:
        """save_all rewrites the file without duplicates."""
        path = tmp_path / "sem.jsonl"
        sm = SemanticMemory(path=path)
        sm.add("m1", "original")
        sm.add("m1", "updated")  # append (duplicate in file)
        sm.save_all()
        # Reload — should have only 1 doc.
        sm2 = SemanticMemory(path=path)
        assert sm2.count() == 1
        assert sm2.get("m1").content == "updated"

    def test_clear_deletes_all(self, tmp_path: Path) -> None:
        """clear() deletes all documents + the file."""
        path = tmp_path / "sem.jsonl"
        sm = SemanticMemory(path=path)
        sm.add("m1", "doc one")
        sm.add("m2", "doc two")
        n = sm.clear()
        assert n == 2
        assert sm.count() == 0
        assert not path.exists()

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        """Malformed JSONL lines are skipped on load."""
        path = tmp_path / "sem.jsonl"
        path.write_text(
            '{"doc_id":"m1","content":"valid","kind":"memory"}\n'
            'this is not json\n'
            '{"doc_id":"m2","content":"also valid","kind":"memory"}\n',
            encoding="utf-8",
        )
        sm = SemanticMemory(path=path)
        assert sm.count() == 2  # malformed line skipped


class TestIsSemanticMemoryEnabled:
    """Tests for the env-var check."""

    def test_default_on(self, monkeypatch) -> None:
        """Semantic memory is ON by default (opt-out)."""
        monkeypatch.delenv("NEXA_SEMANTIC_MEMORY", raising=False)
        assert is_semantic_memory_enabled() is True

    def test_disabled_when_zero(self, monkeypatch) -> None:
        """NEXA_SEMANTIC_MEMORY=0 disables it."""
        monkeypatch.setenv("NEXA_SEMANTIC_MEMORY", "0")
        assert is_semantic_memory_enabled() is False
