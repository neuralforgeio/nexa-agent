"""
Tests for the ``log_analysis`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. The log file is really read from a
temporary workspace, prompt construction and schema validation run for real.

Honesty invariant under test: the exact bytes of the REAL log file reach the
model prompt, and findings come from the model's reply — the handler never
invents anomalies.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills import registry as R
from skills.devops_operations.log_analysis.handler import handle
from tests._skill_helpers import ScriptedProvider

LOG_TEXT = """\
2026-08-03T10:00:01Z INFO  api-gateway request ok latency_ms=21
2026-08-03T10:00:02Z INFO  api-gateway request ok latency_ms=19
2026-08-03T10:00:03Z ERROR billing    charge failed code=card_declined user=u_9
2026-08-03T10:00:03Z ERROR billing    charge failed code=card_declined user=u_9
2026-08-03T10:00:04Z WARN  api-gateway upstream timeout upstream=inventory
2026-08-03T10:00:05Z CRITICAL database connection refused host=db-primary
"""

GOOD_REPLY = json.dumps(
    {
        "anomalies": [
            {"line": 6, "description": "database connection refused"},
            {"line": 4, "description": "duplicate card_declined retries"},
        ],
        "patterns": [
            "repeated card_declined failures for user u_9",
            "api-gateway request ok with ~20ms latency",
        ],
        "root_cause": "db-primary refusing connections caused cascading upstream timeouts",
        "recommendations": [
            "check db-primary availability and restart it",
            "add retry backoff to billing charge calls",
        ],
    }
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "nexa-agent.log").write_text(LOG_TEXT, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("log_analysis").manifest


def _input(**over):
    base = {
        "log_source": "logs/nexa-agent.log",
        "log_format": "json",
        "analysis_type": "error",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_input_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(analysis_type="forensics"), ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_log_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(_input(log_source="logs/nope.log"), ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path: schema-valid, all required keys, right types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_types(ws):
    out = await handle(_input(), ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert isinstance(out["anomalies"], list) and len(out["anomalies"]) == 2
    assert all(
        set(a.keys()) == {"line", "description"}
        and isinstance(a["line"], int)
        and isinstance(a["description"], str)
        for a in out["anomalies"]
    )
    assert isinstance(out["patterns"], list)
    assert all(isinstance(p, str) for p in out["patterns"])
    assert isinstance(out["root_cause"], str) and "db-primary" in out["root_cause"]
    assert isinstance(out["recommendations"], list)
    assert all(isinstance(r, str) for r in out["recommendations"])


@pytest.mark.asyncio
async def test_empty_anomalies_honoured(ws):
    reply = json.dumps(
        {
            "anomalies": [],
            "patterns": ["steady healthy traffic"],
            "root_cause": "insufficient evidence in the shown log",
            "recommendations": [],
        }
    )
    out = await handle(_input(analysis_type="anomaly"), ScriptedProvider(reply=reply))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["anomalies"] == []
    assert out["recommendations"] == []


# ---------------------------------------------------------------------------
# 3. Prompt fidelity: the REAL log text reaches the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_log_text(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input(), provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "CRITICAL database connection refused host=db-primary" in user_prompt
    assert "charge failed code=card_declined user=u_9" in user_prompt
    assert "error" in user_prompt  # analysis_type passed along
    assert "logs/nexa-agent.log" in user_prompt  # real source named
    assert messages[0]["role"] == "system"
    assert "anomalies" in messages[0]["content"]
    assert "root_cause" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path validates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "log_analysis", _input(), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert "db-primary" in out["root_cause"]


# ---------------------------------------------------------------------------
# 5. LLM failure propagates as RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
