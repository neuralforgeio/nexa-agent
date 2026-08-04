"""
Tests for the ``infrastructure_as_code`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Prompt construction, schema validation,
and the registry executor all run for real. Honesty invariant under test:
the handler must NOT claim pricing — ``estimated_cost`` is always an honest
"pricing API not configured" stub, never fabricated currency numbers.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills import registry as R
from skills.devops_operations.infrastructure_as_code.handler import handle
from tests._skill_helpers import ScriptedProvider

GOOD_REPLY = json.dumps(
    {
        "iac_code": 'resource "aws_s3_bucket" "cdn" {\n  bucket = "example"\n}\n',
        "file_path": "infra/aws/main.tf",
        # Model must not be allowed to fabricate pricing; handler normalises.
        "estimated_cost": {"monthly": "$12.50"},
    }
)

VALID_INPUT = {
    "description": "an S3 bucket with versioning and CloudFront in front",
    "provider": "aws",
    "iac_tool": "terraform",
}


def _manifest():
    return skills.get_skill("infrastructure_as_code").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_input_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_bad_enum_values_raise_input_error():
    with pytest.raises(R.SkillInputError):
        await handle(
            {**VALID_INPUT, "provider": "digitalocean"}, ScriptedProvider()
        )
    with pytest.raises(R.SkillInputError):
        await handle(
            {**VALID_INPUT, "iac_tool": "ansible"}, ScriptedProvider()
        )


# ---------------------------------------------------------------------------
# 2. Happy path: schema-valid, model content normalised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_honest_cost():
    out = await handle(VALID_INPUT, ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert isinstance(out["iac_code"], str) and "aws_s3_bucket" in out["iac_code"]
    assert isinstance(out["file_path"], str) and out["file_path"] == "infra/aws/main.tf"
    # Honest stub: no fabricated pricing currency surfaced.
    assert isinstance(out["estimated_cost"], dict)
    assert out["estimated_cost"].get("note") == (
        "estimate requires pricing API, not configured"
    )
    assert "$12.50" not in json.dumps(out["estimated_cost"])


@pytest.mark.asyncio
async def test_missing_model_file_path_falls_back():
    reply = json.dumps({"iac_code": "terraform {}"})
    out = await handle(VALID_INPUT, ScriptedProvider(reply=reply))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["file_path"] == "infra/aws/main.tf"


# ---------------------------------------------------------------------------
# 3. Prompt fidelity: the real description reaches the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_description():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(VALID_INPUT, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "an S3 bucket with versioning and CloudFront in front" in user_prompt
    assert "aws" in user_prompt
    assert "terraform" in user_prompt
    assert messages[0]["role"] == "system"
    assert "iac_code" in messages[0]["content"]
    assert "file_path" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "infrastructure_as_code",
        VALID_INPUT,
        ScriptedProvider(reply=GOOD_REPLY),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert "aws_s3_bucket" in out["iac_code"]


# ---------------------------------------------------------------------------
# 5. LLM failure propagates as RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(VALID_INPUT, ScriptedProvider(fail=True))
