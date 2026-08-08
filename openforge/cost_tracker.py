"""Cost tracker + usage metering per provider (H-06/H-07)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from openforge.config import FORGE_HOME

_DB = FORGE_HOME / "cost_tracking.db"

# Provider pricing per 1K tokens (USD). Overridden via env if needed.
_PRICING = {
    "openai": 0.0015,         # gpt-4o-mini
    "ollama": 0.0002,         # local
    "tokenrouter": 0.0005,
    "llamacpp": 0.0,
}


def _conn():
    FORGE_HOME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_DB))
    con.execute("""CREATE TABLE IF NOT EXISTS usage(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        provider TEXT,
        model TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        cost_usd REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    return con


def record_usage(session_id: Optional[str], provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = _PRICING.get(provider, 0.001)
    cost = (prompt_tokens + completion_tokens) / 1000.0 * rate
    with _conn() as con:
        con.execute(
            "INSERT INTO usage(session_id, provider, model, prompt_tokens, completion_tokens, cost_usd) VALUES(?,?,?,?,?,?)",
            (session_id, provider, model, prompt_tokens, completion_tokens, cost),
        )
    return cost


def get_usage(days: int = 7, session_id: Optional[str] = None) -> Dict[str, Any]:
    with _conn() as con:
        base = "SELECT provider, model, SUM(prompt_tokens) p, SUM(completion_tokens) c, SUM(cost_usd) cost FROM usage WHERE created_at >= datetime('now', '-%d days')" % days
        if session_id:
            base += " AND session_id = ?"
            rows = con.execute(base + " GROUP BY provider, model", (session_id,)).fetchall()
        else:
            rows = con.execute(base + " GROUP BY provider, model").fetchall()
        total = con.execute("SELECT COALESCE(SUM(cost_usd),0), COUNT(*) FROM usage WHERE created_at >= datetime('now', '-%d days')" % days).fetchone()
    return {
        "total_cost_usd": total[0],
        "total_calls": total[1],
        "by_provider": [{"provider": r[0], "model": r[1], "prompt_tokens": r[2], "completion_tokens": r[3], "cost_usd": r[4]} for r in rows],
    }
