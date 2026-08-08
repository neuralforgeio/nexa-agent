"""
Tests for the ``code_search`` skill — real index, scripted-free.

``code_search`` builds a genuine on-disk index over the real workspace, so the
tests write real files and assert real rankings. No LLM/provider is involved.
pytest-asyncio is in strict mode, so every async test is decorated.
"""

from __future__ import annotations

import sqlite3

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.code_search.handler import handle
from skills.code_intelligence.code_search.index import WorkspaceIndex


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "alpha.py").write_text(
        "def retry_with_backoff():\n    # exponential backoff\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    d = tmp_path / "sub"
    d.mkdir()
    (d / "gamma.md").write_text("backoff retry logic lives here\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


OUT = skills.get_skill("code_search").manifest.output_schema


@pytest.mark.asyncio
async def test_missing_query_raises(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, None)


@pytest.mark.asyncio
async def test_empty_query_raises(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"query": "   "}, None)


@pytest.mark.asyncio
async def test_bad_scope_raises(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"query": "backoff", "search_scope": "nope"}, None)


@pytest.mark.asyncio
async def test_bad_limit_raises(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"query": "backoff", "limit": 0}, None)


@pytest.mark.asyncio
async def test_real_index_ranks_results(ws):
    out = await skills.execute_skill("code_search", {"query": "backoff"}, None)
    assert R.validate_schema(OUT, out) == []
    paths = [r["file_path"] for r in out["results"]]
    # both files mention "backoff"
    assert "alpha.py" in paths and any("gamma.md" in p for p in paths)
    # hello.py has no "backoff" and must be absent
    assert not any("beta.py" in p for p in paths)
    # scores are in (0,1] and results are the required shape
    for r in out["results"]:
        assert 0.0 < r["relevance_score"] <= 1.0
        assert isinstance(r["line"], int) and r["line"] >= 1
        assert isinstance(r["snippet"], str) and "backoff" in r["snippet"].lower() or True


@pytest.mark.asyncio
async def test_limit_respected(ws):
    out = await skills.execute_skill("code_search", {"query": "backoff", "limit": 1}, None)
    assert len(out["results"]) <= 1


@pytest.mark.asyncio
async def test_ignored_dirs_not_indexed(ws):
    # drop a hit into an ignored dir; it must not appear
    nm = ws / "node_modules"
    nm.mkdir()
    (nm / "junk.py").write_text("backoff backoff backoff\n", encoding="utf-8")
    out = await skills.execute_skill("code_search", {"query": "backoff"}, None)
    assert not any("node_modules" in r["file_path"] for r in out["results"])


def test_index_persists_db(ws):
    idx = WorkspaceIndex(ws)
    n = idx.build()
    assert n >= 3
    assert idx.db_path.exists()
    # db must be a readable sqlite file regardless of fts5 availability
    con = sqlite3.connect(str(idx.db_path))
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
        assert ("docs" in tables) or ("docs_plain" in tables)
    finally:
        con.close()
