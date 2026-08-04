"""
Tests for the ``fact_checking`` skill (web_research).

Every async test is explicitly marked — pyproject sets no
``asyncio_mode = "auto"``.
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.fact_checking.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("fact_checking").manifest.output_schema


def _input(**overrides):
    payload = {"claim": "The Python GIL was removed in CPython 3.13."}
    payload.update(overrides)
    return payload


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_or_empty_claim_raise_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle(_input(claim="   "), ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle(_input(claim=123), ScriptedProvider())


# 2. Happy path — schema-valid, verdict normalised and clamped -------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_with_sources():
    reply = (
        '{"verdict": "Partial",'
        ' "evidence": ["Source [1] explicitly says the GIL remains present in 3.13."],'
        ' "confidence": 0.93}'
    )
    result = await handle(
        _input(sources=["Source: CPython 3.13 still ships with the GIL enabled."]),
        ScriptedProvider(reply=reply),
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert set(result) == {"verdict", "evidence", "confidence"}
    assert result["verdict"] == "partial"  # normalised case
    assert isinstance(result["evidence"], list)
    assert all(isinstance(e, str) for e in result["evidence"])
    assert isinstance(result["confidence"], (int, float))
    assert 0.0 <= result["confidence"] <= 1.0


# 3. Honesty: with NO sources the verdict is unverified with empty evidence --------


@pytest.mark.asyncio
async def test_no_sources_yields_unverified_and_no_fabricated_evidence():
    # Even if a model were to hallucinate support, an "unverified" verdict
    # is sanitised to empty evidence so no fabricated citations survive.
    result = await handle(
        _input(),
        ScriptedProvider(reply='{"verdict": "unverified", "evidence": ["made up citation"], "confidence": 0.9}'),
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["verdict"] == "unverified"
    assert result["evidence"] == []
    assert result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_bad_verdict_defaults_to_unverified():
    result = await handle(
        _input(), ScriptedProvider(reply='{"verdict": "mostly-true", "confidence": 0.5}')
    )
    assert result["verdict"] == "unverified"
    assert validate_schema(OUTPUT_SCHEMA, result) == []


# 4. Prompt fidelity — the real claim and sources reach the provider -------------


@pytest.mark.asyncio
async def test_prompt_contains_real_claim_and_sources():
    provider = ScriptedProvider(
        reply='{"verdict": "unverified", "evidence": [], "confidence": 0.0}'
    )
    await handle(_input(sources=["Source: CPython 3.13 docs."]), provider)

    assert provider.calls
    payload = provider.calls[0][-1]["content"]
    assert _input()["claim"] in payload
    assert "Source: CPython 3.13 docs." in payload


# 5. Executor path — full registry round-trip -------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    reply = '{"verdict": "false", "evidence": ["[1] contradicts the claim."], "confidence": 0.87}'
    result = await skills.execute_skill(
        "fact_checking", _input(sources=["[1] The GIL is present in 3.13."]),
        ScriptedProvider(reply=reply),
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["verdict"] == "false"


# 6. LLM failure surfaces, never swallowed ----------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
