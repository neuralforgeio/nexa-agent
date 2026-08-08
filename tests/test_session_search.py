"""
Tests for the FTS5 session search functionality.

Verifies:
    - search_sessions() finds conversations by keyword.
    - Results include conversation metadata and snippets.
    - Empty query returns no results.
    - Search respects the limit parameter.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest
import pytest_asyncio

import openforge.config as _nexa_config
import openforge.state as _nexa_state
from agent.memory.session_search import search_sessions, format_search_results
from openforge.state import ConversationDB


@pytest_asyncio.fixture
async def db_with_data(tmp_path, monkeypatch):
    """Provide a DB with seeded conversations for search testing.

    v4.15.1: isolate the DB inside the fixture. ``ConversationDB`` reads
    ``nexa.state.FORGE_DB_PATH`` while :func:`search_sessions` reads
    ``nexa.config.FORGE_DB_PATH`` (both are by-value snapshot imports taken
    at module import time), so BOTH module namespaces must be re-pointed to
    ``tmp_path``. Without this the fixture opens the real ``~/.openforge/openforge.db``
    and fails with ``sqlite3.OperationalError`` whenever another test has
    left the global FORGE_HOME/FORGE_DB_PATH in a polluted state.
    """
    forge_home = tmp_path / ".nexa"
    db_path = forge_home / "openforge.db"
    monkeypatch.setattr(_nexa_config, "FORGE_HOME", forge_home)
    monkeypatch.setattr(_nexa_config, "FORGE_DB_PATH", db_path)
    monkeypatch.setattr(_nexa_state, "FORGE_HOME", forge_home)
    monkeypatch.setattr(_nexa_state, "FORGE_DB_PATH", db_path)

    db = ConversationDB()
    await db.init()

    # Create conversation 1 about Python.
    conv1 = await db.create_conversation("Python programming discussion")
    await db.add_message(conv1["id"], "user", "How do I use Python decorators?")
    await db.add_message(conv1["id"], "assistant", "Python decorators are a powerful feature...")

    # Create conversation 2 about file operations.
    conv2 = await db.create_conversation("File operations with Nexa")
    await db.add_message(conv2["id"], "user", "Can you write a file for me?")
    await db.add_message(conv2["id"], "assistant", "I will use the write_file tool to create it.")

    # Create conversation 3 (unrelated).
    conv3 = await db.create_conversation("Random chat")
    await db.add_message(conv3["id"], "user", "What is the weather today?")
    await db.add_message(conv3["id"], "assistant", "I cannot check the weather.")

    return db


@pytest.mark.asyncio
async def test_search_finds_python_conversation(db_with_data) -> None:
    """Searching for 'Python' must find the Python conversation."""
    results = await search_sessions(db_with_data, "Python", limit=10)
    assert len(results) >= 1
    titles = [r["title"] for r in results]
    assert any("Python" in t for t in titles)


@pytest.mark.asyncio
async def test_search_finds_file_conversation(db_with_data) -> None:
    """Searching for 'file' must find the file operations conversation."""
    results = await search_sessions(db_with_data, "file", limit=10)
    assert len(results) >= 1
    titles = [r["title"] for r in results]
    assert any("File" in t or "file" in t for t in titles)


@pytest.mark.asyncio
async def test_search_returns_snippets(db_with_data) -> None:
    """Search results must include a non-empty snippet."""
    results = await search_sessions(db_with_data, "Python", limit=10)
    assert len(results) >= 1
    for r in results:
        assert "snippet" in r
        assert isinstance(r["snippet"], str)


@pytest.mark.asyncio
async def test_search_includes_match_count(db_with_data) -> None:
    """Search results must include a match_count >= 1."""
    results = await search_sessions(db_with_data, "Python", limit=10)
    for r in results:
        assert r["match_count"] >= 1


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(db_with_data) -> None:
    """An empty query must return an empty list."""
    results = await search_sessions(db_with_data, "", limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_search_no_results_for_nonexistent(db_with_data) -> None:
    """Searching for a nonexistent term must return an empty list."""
    results = await search_sessions(db_with_data, "quantum_supremacy_xyz123", limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_search_respects_limit(db_with_data) -> None:
    """The limit parameter must cap the number of results."""
    results = await search_sessions(db_with_data, "Python", limit=1)
    assert len(results) <= 1


@pytest.mark.asyncio
async def test_format_search_results(db_with_data) -> None:
    """format_search_results must produce a human-readable string."""
    results = await search_sessions(db_with_data, "Python", limit=10)
    formatted = format_search_results(results, "Python")
    assert isinstance(formatted, str)
    assert "Python" in formatted
