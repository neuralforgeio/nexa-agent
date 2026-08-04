"""
Tests for the ``etl_pipeline`` skill (data_analytics).

The LLM generates pipeline code text; a real ``compile()`` syntax check runs in
code when the text looks like Python. Every async test is marked (pytest-asyncio
strict). No pipeline is ever deployed.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.data_analytics.etl_pipeline.handler import handle
from tests._skill_helpers import ScriptedProvider

SOURCE = {"type": "csv", "path": "data/raw_events.csv"}
DESTINATION = {"type": "postgres", "table": "events"}
TRANSFORMATIONS = [
    {"op": "dedupe", "key": "event_id"},
    {"op": "cast", "column": "ts", "to": "timestamp"},
]

GOOD_REPLY = (
    '{"pipeline_code": "import csv\\n'
    'def extract():\\n'
    '    return list(csv.DictReader(open(\'data/raw_events.csv\')))\\n'
    'def run():\\n'
    '    extract()", '
    '"notes": "Uses csv.DictReader for extraction."}'
)


def _manifest():
    return skills.get_skill("etl_pipeline").manifest


def _input():
    return {
        "source": SOURCE,
        "destination": DESTINATION,
        "transformations": TRANSFORMATIONS,
        "schedule": "0 * * * *",
    }


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle({"source": SOURCE, "destination": DESTINATION}, ScriptedProvider())


# 2. Schema conformance + honest test_results -----------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_real_syntax_check():
    out = await handle(_input(), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Code text came from the model's reply.
    assert "csv.DictReader" in out["pipeline_code"]
    # Config echoes the real input.
    assert out["pipeline_config"]["source"] == SOURCE
    assert out["pipeline_config"]["destination"] == DESTINATION
    assert out["pipeline_config"]["schedule"] == "0 * * * *"
    # A real compile() ran on the valid Python -> ok True, honest status.
    assert out["test_results"]["status"] == "code_generated_not_executed"
    assert out["test_results"]["ok"] is True
    check = out["test_results"]["checks"][0]
    assert check["name"] == "python_syntax_compile"
    assert check["ok"] is True


@pytest.mark.asyncio
async def test_fallback_code_when_model_returns_empty():
    out = await handle(_input(), ScriptedProvider(reply='{"pipeline_code": "", "notes": ""}'))
    assert R.validate_schema(_manifest().output_schema, out) == []
    # Code-derived skeleton references the real configs.
    assert "raw_events.csv" in out["pipeline_code"]
    assert "def extract" in out["pipeline_code"]
    # The deterministic skeleton is valid Python and compiles ok.
    assert out["test_results"]["ok"] is True


# 3. Prompt fidelity -----------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_configs_and_steps():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input(), provider)
    assert provider.calls
    user = provider.calls[0][-1]["content"]
    # Real source/destination/transformations reached the model.
    assert "raw_events.csv" in user
    assert '"postgres"' in user
    assert "dedupe" in user
    assert "event_id" in user
    assert provider.calls[0][0]["role"] == "system"


# 4. Executor path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill("etl_pipeline", _input(), ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["pipeline_config"]["transformations"] == TRANSFORMATIONS


# 5. LLM failure surfaces ------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
