"""
Tests for the ``data_analysis`` skill (data_analytics).

Real file reads and statistics computed in code run against a temp workspace
(``FORGE_WORKSPACE`` -> ``tmp_path``). The LLM boundary uses a scripted provider;
every async test is marked (pytest-asyncio strict).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.data_analytics.data_analysis.handler import handle
from tests._skill_helpers import ScriptedProvider

CSV = (
    "day,signups,revenue\n"
    "Mon,10,100\n"
    "Tue,20,200\n"
    "Wed,30,300\n"
    "Thu,40,400\n"
    "Fri,50,500\n"
)
# signups mean = 30.0, revenue mean = 300.0; perfect positive correlation (1.0).
CSV_PATH = "data/sales.csv"

GOOD_REPLY = (
    '{"insights": [{"finding": "Signups rose steadily across the week.", '
    '"evidence": "signups mean=30.0, min=10, max=50.", '
    '"recommendation": "Investigate what drove Friday signups."}], '
    '"statistics": {"note": "model echo"}}'
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sales.csv").write_text(CSV, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("data_analysis").manifest


def _input(analysis_type="summary"):
    return {"data_source": CSV_PATH, "analysis_type": analysis_type}


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle({"data_source": CSV_PATH}, ScriptedProvider())


@pytest.mark.asyncio
async def test_bad_analysis_type_and_missing_file_raise(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"data_source": CSV_PATH, "analysis_type": "bogus"}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle({"data_source": "nope.csv", "analysis_type": "summary"}, ScriptedProvider())


# 2. Schema conformance + honest computed statistics ----------------------------


@pytest.mark.asyncio
async def test_summary_statistics_match_real_csv(ws):
    out = await handle(_input("summary"), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    stats = out["statistics"]
    # Code-computed from the real CSV, not from the model.
    assert stats["row_count"] == 5
    assert stats["columns_stats"]["signups"]["mean"] == 30.0
    assert stats["columns_stats"]["revenue"]["max"] == 500.0
    assert out["visualizations"] == []
    # Insight keys conform to the per-item schema.
    assert set(out["insights"][0]) == {"finding", "evidence", "recommendation"}


@pytest.mark.asyncio
async def test_correlation_matrix_computed_in_code(ws):
    out = await handle(_input("correlation"), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    matrix = out["statistics"]["correlation_matrix"]
    # signups vs revenue is perfectly linear in the CSV -> ~1.0.
    assert matrix["signups"]["revenue"] == 1.0
    assert matrix["signups"]["signups"] == 1.0


# 3. Prompt fidelity -----------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_stats_and_data(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input("summary"), provider)
    assert provider.calls
    user = provider.calls[0][-1]["content"]
    # Real computed stats reached the model.
    assert '"row_count": 5' in user
    assert "signups" in user
    # Real sample data rows reached the model.
    assert "Mon,10,100" in user
    # System turn pins the JSON contract.
    assert provider.calls[0][0]["role"] == "system"


# 4. Executor path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill("data_analysis", _input("summary"), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["statistics"]["columns_stats"]["signups"]["mean"] == 30.0


# 5. LLM failure surfaces ------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await handle(_input("summary"), ScriptedProvider(fail=True))
