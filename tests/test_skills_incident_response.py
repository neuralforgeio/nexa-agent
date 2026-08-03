"""
Tests for the ``incident_response`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Prompt construction, schema validation,
and the registry executor all run for real.

Honesty invariants under test: ``escalation`` is always the fixed placeholder
("state": "suggest_only"), ``safe_to_auto_execute`` defaults to False unless
the model explicitly flags it, and nothing ever claims the incident was
resolved.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills import registry as R
from skills.devops_operations.incident_response.handler import handle
from tests._skill_helpers import ScriptedProvider

INCIDENT = "API 5xx rate spiked to 40% after the 14:20 deploy"

GOOD_REPLY = json.dumps(
    {
        "triage": {
            "summary": "Likely bad deploy to api-gateway at 14:20 causing 5xx",
            "urgency": "immediate",
            "impact": "40% of API traffic failing; billing calls erroring",
            "owner": "on-call-sre",
        },
        "runbook_steps": [
            {
                "step": 1,
                "command": "kubectl rollout status deploy/api-gateway",
                "safe_to_auto_execute": True,
            },
            {
                "step": 2,
                "command": "kubectl rollout undo deploy/api-gateway",
                "safe_to_auto_execute": False,
            },
            {"command": "page the incident commander"},  # no step number
        ],
        # The model must not be allowed to claim escalation happened.
        "escalation": {"state": "notified", "contacts": ["real-person@corp.com"]},
    }
)


def _manifest():
    return skills.get_skill("incident_response").manifest


def _input(**over):
    base = {
        "incident_description": INCIDENT,
        "severity": "P1",
        "affected_services": ["api-gateway", "billing"],
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_input_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(severity="P9"), ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(_input(affected_services=[]), ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path: schema-valid, honest escalation stub, strict safety default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_honesty():
    out = await handle(_input(), ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []

    triage = out["triage"]
    assert isinstance(triage, dict)
    assert "14:20" in triage["summary"]  # grounded in the real description
    assert triage["severity"] == "P1"
    assert triage["affected_services"] == ["api-gateway", "billing"]
    assert triage["urgency"] == "immediate"
    assert triage["owner"] == "on-call-sre"

    steps = out["runbook_steps"]
    assert len(steps) == 3
    for s in steps:
        assert set(s.keys()) == {"step", "command", "safe_to_auto_execute"}
        assert isinstance(s["step"], int) and s["step"] >= 1
        assert isinstance(s["command"], str)
        assert isinstance(s["safe_to_auto_execute"], bool)
    assert steps[0]["safe_to_auto_execute"] is True   # model said read-only
    assert steps[1]["safe_to_auto_execute"] is False  # mutating rollback
    assert steps[2]["safe_to_auto_execute"] is False  # missing -> strict False
    assert steps[2]["step"] == 3  # positional fallback for missing number

    # Escalation is the honest placeholder, never the model's fiction.
    assert out["escalation"] == {
        "state": "suggest_only",
        "contacts": ["team-lead@example.com"],
    }


@pytest.mark.asyncio
async def test_missing_triage_fields_use_severity_defaults():
    reply = json.dumps({"runbook_steps": []})
    out = await handle(_input(severity="P0"), ScriptedProvider(reply=reply))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["triage"]["urgency"] == "immediate"
    assert out["triage"]["owner"] == "incident-commander"
    assert out["triage"]["severity"] == "P0"
    assert out["runbook_steps"] == []


# ---------------------------------------------------------------------------
# 3. Prompt fidelity: the REAL incident text reaches the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_incident():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(_input(), provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "API 5xx rate spiked to 40% after the 14:20 deploy" in user_prompt
    assert '"api-gateway"' in user_prompt and '"billing"' in user_prompt
    assert "P1" in user_prompt
    assert messages[0]["role"] == "system"
    assert "triage" in messages[0]["content"]
    assert "runbook_steps" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path validates; invalid enum rejected before handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "incident_response", _input(), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["escalation"]["state"] == "suggest_only"


@pytest.mark.asyncio
async def test_execute_skill_rejects_bad_severity_before_handler():
    with pytest.raises(R.SkillInputError):
        await skills.execute_skill(
            "incident_response", _input(severity="P9"), ScriptedProvider()
        )


# ---------------------------------------------------------------------------
# 5. LLM failure propagates as RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
