"""
Tests for the ``monitoring_setup`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Directory listing, prompt construction,
schema validation, and the registry executor all run for real against a
temporary workspace.

Honesty invariants under test: ``dashboard_url`` is always "" (no dashboard
was ever created) even if the model claims one, and the workspace is left
byte-for-byte unchanged (configs are returned, not installed).
"""

from __future__ import annotations

import json

import pytest

import skills
from skills import registry as R
from skills.devops_operations.monitoring_setup.handler import handle
from tests._skill_helpers import ScriptedProvider

GOOD_REPLY = json.dumps(
    {
        "config_files": [
            {
                "path": "monitoring/prometheus.yml",
                "content": (
                    "scrape_configs:\n"
                    "  - job_name: api\n"
                    "    metrics_path: /metrics\n"
                ),
            },
            {
                "path": "monitoring/alerts.yml",
                "content": "groups:\n  - name: error_rate\n    rules: []\n",
            },
        ],
        # The model must not be allowed to pretend a dashboard exists.
        "dashboard_url": "http://grafana.example.com/d/abc",
    }
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    app = tmp_path / "agent"
    app.mkdir()
    (app / "server.py").write_text("# api server\n", encoding="utf-8")
    (app / "worker.py").write_text("# worker\n", encoding="utf-8")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("monitoring_setup").manifest


def _input(**over):
    base = {
        "app_path": "agent",
        "metrics": ["request_latency", "error_rate"],
        "alerting": {"channel": "slack", "threshold": "error_rate > 0.05"},
        "platform": "prometheus",
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
        await handle(_input(metrics=[]), ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(platform="splunk"), ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_app_dir_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="not a directory"):
        await handle(_input(app_path="nope"), ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path: schema-valid, model content kept, honest dashboard_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_and_honest_dashboard_url(ws):
    out = await handle(_input(), ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert len(out["config_files"]) == 2
    for cf in out["config_files"]:
        assert set(cf.keys()) == {"path", "content"}
        assert isinstance(cf["path"], str) and isinstance(cf["content"], str)
    assert out["config_files"][0]["path"] == "monitoring/prometheus.yml"
    assert "scrape_configs" in out["config_files"][0]["content"]
    # Model's claimed dashboard URL is dropped — none was created.
    assert out["dashboard_url"] == ""
    # Nothing was written into the workspace.
    assert not (ws / "monitoring").exists()


# ---------------------------------------------------------------------------
# 3. Prompt fidelity: the REAL metrics / alerting / listing reach the LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_metrics_and_alerting(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input(), provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "request_latency" in user_prompt
    assert "error_rate > 0.05" in user_prompt
    assert '"channel": "slack"' in user_prompt
    # Real directory listing read from the workspace reaches the prompt.
    assert "server.py" in user_prompt and "worker.py" in user_prompt
    assert messages[0]["role"] == "system"
    assert "config_files" in messages[0]["content"]
    assert "dashboard_url" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path validates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "monitoring_setup", _input(), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["dashboard_url"] == ""


# ---------------------------------------------------------------------------
# 5. LLM failure propagates as RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
