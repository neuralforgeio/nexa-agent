"""
Tests for the ``chart_generation`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Prompt construction, schema validation,
and the registry executor all run for real.

Honesty invariant under test: ``chart_code`` must be the model's real reply
to a prompt that embeds the *actual* data rows, and ``image_path`` must
honestly be ``""`` — the generated code is deliberately NEVER executed (no
arbitrary code execution by default), so no image file is fabricated.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.chart_generation.handler import handle
from tests._skill_helpers import ScriptedProvider

DATA = [
    {"quarter": "Q1", "revenue": 12.4},
    {"quarter": "Q2", "revenue": 15.1},
    {"quarter": "Q3", "revenue": 9.8},
    {"quarter": "Q4", "revenue": 18.3},
]

GOOD_REPLY = (
    "import matplotlib.pyplot as plt\n"
    "quarters = ['Q1', 'Q2', 'Q3', 'Q4']\n"
    "revenue = [12.4, 15.1, 9.8, 18.3]\n"
    "plt.bar(quarters, revenue)\n"
    "plt.title('Quarterly revenue')\n"
    "plt.savefig('chart.png')\n"
)

GOOD_INPUT = {
    "data": DATA,
    "chart_type": "bar",
    "title": "Quarterly revenue",
}


def _manifest():
    return skills.get_skill("chart_generation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_data_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle(
            {"chart_type": "bar", "title": "Quarterly revenue"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_bad_chart_type_raises_input_error():
    with pytest.raises(R.SkillInputError, match="chart_type"):
        await handle({**GOOD_INPUT, "chart_type": "radar"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_bad_options_type_raises_input_error():
    with pytest.raises(R.SkillInputError, match="options"):
        await handle({**GOOD_INPUT, "options": "wide"}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path + schema — honest: code from the model, no image fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema():
    out = await handle(GOOD_INPUT, ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["chart_code"].startswith("import matplotlib")
    assert "plt.bar" in out["chart_code"]
    # Honest: code is generated but NOT executed, so no image exists.
    assert out["image_path"] == ""


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real data rows reached the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_data():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(GOOD_INPUT, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "Q1" in user_prompt
    assert "12.4" in user_prompt
    assert "18.3" in user_prompt
    assert "Quarterly revenue" in user_prompt
    assert "bar" in user_prompt
    assert messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "chart_generation", dict(GOOD_INPUT), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["chart_code"].startswith("import matplotlib")
    assert out["image_path"] == ""


# ---------------------------------------------------------------------------
# 5. LLM failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(GOOD_INPUT, ScriptedProvider(fail=True))
