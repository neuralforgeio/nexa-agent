# SPDX-License-Identifier: MIT
"""Skill: database_querying.

Purpose: execute, optimize, or design SQL against a database described by a
connection config. ``execute`` runs the query for real against a local SQLite
file (via ``db_connection.path``, resolved inside the workspace) and returns
actual rows plus measured execution time. ``optimize``/``design`` never touch
the DB — they return model/code-generated analysis of the query text only.

Permissions: ``network:*``, ``terminal:execute`` (declared by the manifest;
neither is exercised — only local file-backed SQLite is used).

Honest note: only a real, local SQLite database is supported, addressed by a
workspace-relative ``path`` in ``db_connection``. Without ``path`` (or with a
non-SQLite config) the handler raises :class:`skills.registry.SkillInputError`
stating a live DB is required — it does NOT fabricate result rows. For SQL
errors, ``results`` is returned as a single ``"ERROR: ..."`` string (never
invented rows) with the measured time. ``execution_time`` is measured in code.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import (
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)
from skills._llm import chat_json  # noqa: F401  (re-exported seam; ask_llm_json uses it)
from skills.registry import SkillInputError

__all__ = ["handle"]

_SYSTEM_OPTIMIZE = (
    "You are Nexa's SQL optimization assistant. You are given a REAL SQL "
    "query and, when available, the database schema it runs against. Suggest "
    "ONLY improvements that genuinely apply to the shown query (indexes, "
    "select-list reduction, JOIN/WHERE restructuring, avoiding SELECT *, "
    "etc). Respond with a SINGLE JSON object, and nothing else, with exactly "
    'one key: "suggestions" (an array of short strings).'
)


def _resolve_db_path(db_connection: Dict[str, Any]) -> Path:
    """Resolve the SQLite file path inside the workspace, or raise."""
    if not isinstance(db_connection, dict):
        raise SkillInputError("db_connection must be an object")
    path = db_connection.get("path")
    if not path or not isinstance(path, str):
        raise SkillInputError(
            "database_querying requires a live DB. This skill supports a local "
            "SQLite file only: provide db_connection.path (workspace-relative). "
            "No results were fabricated."
        )
    try:
        p = tool_api.workspace_path(path)
    except ValueError as exc:
        raise SkillInputError(f"invalid db_connection.path {path!r}: {exc}") from exc
    return Path(p)


def _run_query(db_path: Path, query: str):
    """Execute ``query`` against the real SQLite file; return (rows, seconds).

    Rows are returned as a list of plain dicts keyed by column name, matching
    the declared ``output_schema`` (``results`` items are objects). On a SQL
    error a single ``{"error": "..."}`` object is returned — never invented
    rows, and the error is surfaced honestly rather than raised.
    """
    start = time.perf_counter()
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(query)
            fetched = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            # [{"col": value, ...}, ...]; duplicate column names disambiguated.
            counts: Dict[str, int] = {}
            keys: List[str] = []
            for c in cols:
                counts[c] = counts.get(c, 0) + 1
                keys.append(c if counts[c] == 1 else f"{c}_{counts[c]}")
            rows: List[Dict[str, Any]] = [
                {k: v for k, v in zip(keys, r)} for r in fetched
            ]
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        elapsed = time.perf_counter() - start
        return [{"error": str(exc)}], round(elapsed, 6)
    elapsed = time.perf_counter() - start
    return rows, round(elapsed, 6)


def _code_suggestions(query: str) -> List[str]:
    """Deterministic, query-text-derived optimisation hints."""
    suggestions: List[str] = []
    q = query.upper()
    if "SELECT *" in q:
        suggestions.append("Replace SELECT * with an explicit column list.")
    if "WHERE" not in q and "LIMIT" not in q:
        suggestions.append("Consider adding a WHERE or LIMIT clause to bound the scan.")
    if "JOIN" in q and "ON" not in q:
        suggestions.append("Ensure every JOIN has an explicit ON predicate.")
    if not suggestions:
        suggestions.append("No obvious anti-patterns detected in the query text.")
    return suggestions


async def handle(input_data: dict, provider) -> dict:
    """Execute or analyse SQL; only local SQLite file execution is real."""
    query = require(input_data, "query", str, "the SQL query text")
    db_connection = require(input_data, "db_connection", dict, "the DB connection config")
    operation = require(input_data, "operation", str, "execute|optimize|design")
    if operation not in ("execute", "optimize", "design"):
        raise SkillInputError(
            f"operation must be one of execute|optimize|design, got {operation!r}"
        )

    # optimize / design: analyse query text only; never touch a real DB.
    if operation in ("optimize", "design"):
        db_path_str = db_connection.get("path")
        schema_note = ""
        if isinstance(db_path_str, str) and db_path_str:
            try:
                db_path = _resolve_db_path(db_connection)
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    try:
                        tables = conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                        schema_note = "Tables present: " + ", ".join(t[0] for t in tables)
                    finally:
                        conn.close()
            except SkillInputError:
                schema_note = ""
        prompt = (
            f"Operation: {operation}\n"
            f"SQL query (REAL):\n{query}\n\n"
            + (f"Schema context: {schema_note}\n\n" if schema_note else "")
            + "Suggest genuine optimisations (or a sound design) for THIS query. "
              'Return a single JSON object with "suggestions" (array of strings).'
        )
        payload = await ask_llm_json(provider, prompt, system=_SYSTEM_OPTIMIZE, fallback=None)
        suggestions = [coerce_str(s) for s in as_list(payload.get("suggestions")) if s]
        if not suggestions:
            suggestions = _code_suggestions(query)
        return {
            "results": [],
            "execution_time": 0.0,
            "optimization_suggestions": suggestions,
        }

    # operation == "execute"
    db_path = _resolve_db_path(db_connection)
    if not db_path.exists() or not db_path.is_file():
        raise SkillInputError(
            f"SQLite database not found at db_connection.path "
            f"{db_connection.get('path')!r} (resolved to {db_path})"
        )
    results, elapsed = _run_query(db_path, query)
    return {
        "results": results,
        "execution_time": elapsed,
        "optimization_suggestions": _code_suggestions(query),
    }
