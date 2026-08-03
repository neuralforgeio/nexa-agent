"""
Tests for the ``sentiment_analysis`` skill (web_research).

Every async test is explicitly marked — pyproject sets no
``asyncio_mode = "auto"`` (pytest-asyncio strict).
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.sentiment_analysis.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("sentiment_analysis").manifest.output_schema

REPLY = (
    '{"sentiment": "NEGATIVE",'
    ' "score": -0.82,'
    ' "emotions": [{"emotion": "frustration", "intensity": 0.9},'
    '               {"emotion": "anger", "intensity": 5}],'
    ' "intent": "complaining about an outage"}'
)


def _input() -> dict:
    return {
        "text": "Honestly the new release broke our whole pipeline and support never replied.",
        "detail_level": "detailed",
    }


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_text_raises_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle({"detail_level": "basic"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_wrong_type_and_empty_text_raise_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle({"text": 42, "detail_level": "basic"}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle({**_input(), "text": "   "}, ScriptedProvider())


# 2. Happy path — schema-valid, normalisation, clamping -----------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_and_normalised():
    result = await handle(_input(), ScriptedProvider(reply=REPLY))

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert set(result) == {"sentiment", "score", "emotions", "intent"}
    # Case was normalised into the manifest enum.
    assert result["sentiment"] == "negative"
    assert isinstance(result["sentiment"], str)
    assert isinstance(result["score"], (int, float))
    assert -1.0 <= result["score"] <= 1.0
    # Out-of-range intensity was clamped to the schema's 0..1 range.
    assert all(0.0 <= e["intensity"] <= 1.0 for e in result["emotions"])
    assert isinstance(result["intent"], str)


# 3. Normalisation of junk verdict falls back honestly to neutral -------------


@pytest.mark.asyncio
async def test_unrecognised_sentiment_defaults_to_neutral():
    result = await handle(_input(), ScriptedProvider(reply='{"sentiment": "Enraged"}'))
    assert result["sentiment"] == "neutral"
    assert validate_schema(OUTPUT_SCHEMA, result) == []


# 4. Prompt fidelity — the real text reaches the provider ----------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_text_and_detail_level():
    provider = ScriptedProvider(reply=REPLY)
    await handle(_input(), provider)

    assert provider.calls
    payload = provider.calls[0][-1]["content"]
    assert _input()["text"] in payload
    assert "detailed" in payload


# 5. Executor path — full registry round-trip -----------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    result = await skills.execute_skill(
        "sentiment_analysis", _input(), ScriptedProvider(reply=REPLY)
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["sentiment"] == "negative"


# 6. LLM failure surfaces, never swallowed --------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
