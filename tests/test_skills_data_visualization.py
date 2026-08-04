"""
Tests for the ``data_visualization`` skill (data_analytics).

The LLM boundary is scripted; data summarisation runs in code for real. Every
async test is marked (pytest-asyncio strict). ``dashboard_path`` is honestly
empty — no rendering is performed.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.data_analytics.data_visualization.handler import handle
from tests._skill_helpers import ScriptedProvider

DATA = [
    {"day": "Mon", "signups": 34},
    {"day": "Tue", "signups": 51},
    {"day": "Wed", "signups": 42},
]

GOOD_REPLY = (
    '{"components": ["header", "line chart: signups by day", "summary table"], '
    '"description": "Dashboard with a signups line chart over three days."}'
)


def _manifest():
    return skills.get_skill("data_visualization").manifest


def _input(viz_type="dashboard"):
    return {"data": DATA, "viz_type": viz_type, "layout": {"columns": 2}}


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle({"data": DATA}, ScriptedProvider())  # missing viz_type
    with pytest.raises(R.SkillInputError):
        await handle({"data": "not-a-list", "viz_type": "dashboard"}, ScriptedProvider())


# 2. Schema conformance + honest empty path -------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_empty_dashboard_path():
    out = await handle(_input("dashboard"), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Honest: no rendering, so the path is empty — never a fake path.
    assert out["dashboard_path"] == ""
    assert out["components"] == ["header", "line chart: signups by day", "summary table"]
    assert isinstance(out["description"], str) and out["description"]


@pytest.mark.asyncio
async def test_fallback_components_when_model_returns_none():
    out = await handle(_input("report"), ScriptedProvider(reply='{"components": [], "description": ""}'))
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Code-derived fallback mentions the real row count and numeric column.
    assert any("3 data rows" in c for c in out["components"])
    assert any("signups" in c for c in out["components"])
    assert out["description"]  # non-empty fallback


# 3. Prompt fidelity -----------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_data():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input("chart"), provider)
    assert provider.calls
    user = provider.calls[0][-1]["content"]
    # Real data rows and computed stats reached the model.
    assert '"signups": 34' in user or "signups" in user
    assert '"row_count": 3' in user
    assert "chart" in user
    assert '"columns": 2' in user  # layout hint
    assert provider.calls[0][0]["role"] == "system"


# 4. Executor path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill("data_visualization", _input("dashboard"), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["dashboard_path"] == ""


# 5. LLM failure surfaces ------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input("dashboard"), ScriptedProvider(fail=True))
