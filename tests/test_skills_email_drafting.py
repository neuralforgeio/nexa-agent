"""
Tests for the ``email_drafting`` skill (communication).

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Prompt construction, input/output schema
validation, and the registry executor all run for real.

Note: pytest-asyncio runs in STRICT mode in this repo, so every coroutine
test is explicitly decorated with ``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.communication.email_drafting.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("email_drafting").manifest.output_schema

GOOD_REPLY = (
    '{"email_subject": "Q2 results — sign-off needed by Friday",'
    ' "email_body": "Hi Finance Team,\\n\\nPlease find the Q2 results attached.'
    ' Budget is unchanged. We need your sign-off by Friday.\\n\\nBest regards",'
    ' "alternatives": ["Q2 results attached", "Sign-off request: Q2 results"]}'
)


def _valid_input() -> dict:
    return {
        "bullet_points": [
            "Q2 results attached",
            "need sign-off by Friday",
            "budget unchanged",
        ],
        "tone": "formal",
        "recipient": "Finance Team",
        "include_signature": True,
    }


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    # bullet_points present but tone/recipient missing
    with pytest.raises(R.SkillInputError):
        await handle({"bullet_points": ["a"]}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(
            {"bullet_points": ["a"], "tone": "formal"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_wrong_type_raises_input_error():
    bad = _valid_input()
    bad["bullet_points"] = "not-a-list"
    with pytest.raises(R.SkillInputError):
        await handle(bad, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path — output validates against the manifest output_schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await handle(_valid_input(), provider)

    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    assert isinstance(out["email_subject"], str) and out["email_subject"]
    assert isinstance(out["email_body"], str) and out["email_body"]
    assert isinstance(out["alternatives"], list)
    assert all(isinstance(a, str) for a in out["alternatives"])
    assert len(out["alternatives"]) == 2


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the REAL bullets/tone/recipient reach the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_input():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_valid_input(), provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    for bullet in _valid_input()["bullet_points"]:
        assert bullet in user_prompt
    assert "formal" in user_prompt
    assert "Finance Team" in user_prompt
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "email_subject" in messages[0]["content"]
    assert "email_body" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "email_drafting", _valid_input(), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    assert "Q2" in out["email_subject"]


# ---------------------------------------------------------------------------
# 5. LLM failure surfaces, never swallowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_raises_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_valid_input(), ScriptedProvider(fail=True))


# ---------------------------------------------------------------------------
# 6. Junk model output — refuse to fabricate an email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_junk_model_output_raises_value_error():
    provider = ScriptedProvider(reply="Sorry, I cannot draft that.")
    with pytest.raises(ValueError):
        await handle(_valid_input(), provider)
