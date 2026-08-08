"""
Tests for the ``database_querying`` skill (data_analytics).

``execute`` runs against a REAL SQLite file in the temp workspace and returns
actual rows plus a measured time. ``optimize``/``design`` use a scripted LLM.
Every async test is marked (pytest-asyncio strict).
"""

from __future__ import annotations

import sqlite3

import pytest

import skills
from skills import registry as R
from skills.data_analytics.database_querying.handler import handle
from tests._skill_helpers import ScriptedProvider

DB_PATH = "data/app.db"

OPT_REPLY = '{"suggestions": ["Add an index on users.plan for the GROUP BY."]}'


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    db = tmp_path / "data" / "app.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, plan TEXT, age INTEGER)")
    conn.executemany(
        "INSERT INTO users (plan, age) VALUES (?, ?)",
        [("free", 25), ("pro", 40), ("free", 30), ("pro", 35)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("database_querying").manifest


def _execute_input():
    return {
        "query": "SELECT plan, COUNT(*) FROM users GROUP BY plan",
        "db_connection": {"dialect": "sqlite", "path": DB_PATH},
        "operation": "execute",
    }


def _optimize_input():
    return {
        "query": "SELECT * FROM users",
        "db_connection": {"dialect": "sqlite", "path": DB_PATH},
        "operation": "optimize",
    }


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle({"query": "SELECT 1", "operation": "execute"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_execute_without_db_path_raises_skill_input_error(ws):
    payload = _execute_input()
    payload["db_connection"] = {"dialect": "postgres"}  # no path -> honest error
    with pytest.raises(R.SkillInputError) as excinfo:
        await handle(payload, ScriptedProvider())
    assert "live DB" in str(excinfo.value) or "path" in str(excinfo.value)


# 2. Real execution against the real SQLite file --------------------------------


@pytest.mark.asyncio
async def test_execute_returns_real_rows_and_time(ws):
    out = await handle(_execute_input(), ScriptedProvider())
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Real rows from the real DB, as dicts keyed by column name (duplicated
    # aggregate column names are uniquified). free:2 and pro:2, order-agnostic.
    counts = {row["plan"]: row.get("COUNT(*)", row.get("COUNT(*)_2")) for row in out["results"]}
    assert counts == {"free": 2, "pro": 2}
    assert isinstance(out["execution_time"], (int, float))
    assert out["execution_time"] >= 0.0


@pytest.mark.asyncio
async def test_sql_error_returned_honestly_not_raised(ws):
    payload = _execute_input()
    payload["query"] = "SELECT * FROM no_such_table"
    out = await handle(payload, ScriptedProvider())
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Error surfaced as an object with an "error" key; rows never fabricated.
    assert out["results"] and "error" in out["results"][0]
    assert "no_such_table" in out["results"][0]["error"]


# 3. Optimize path (LLM) + prompt fidelity --------------------------------------


@pytest.mark.asyncio
async def test_optimize_returns_model_suggestions_and_prompt_has_query(ws):
    provider = ScriptedProvider(reply=OPT_REPLY)
    out = await handle(_optimize_input(), provider)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["results"] == []  # optimize never touches the DB
    assert out["execution_time"] == 0.0
    assert "index on users.plan" in out["optimization_suggestions"][0]
    # The real query text reached the model.
    assert provider.calls
    assert "SELECT * FROM users" in provider.calls[0][-1]["content"]


# 4. Executor path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill("database_querying", _execute_input(), ScriptedProvider())
    assert R.validate_schema(_manifest().output_schema, out) == []
    plans = {row["plan"] for row in out["results"]}
    assert plans == {"free", "pro"}
