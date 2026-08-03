"""
Tests for the ``realtime_translation`` skill (communication).

This skill is an HONEST graceful-degradation stub: real bidirectional
streaming translation needs ASR + MT + TTS infrastructure that is not
present in this runtime, so the handler returns a schema-valid, honestly
"not available" result — ``translated_stream`` is empty and ``latency`` is
0.0. It never fabricates a stream reference or a latency figure, and never
raises just because the infrastructure is absent.

Note: pytest-asyncio runs in STRICT mode in this repo, so every coroutine
test is explicitly decorated with ``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.communication.realtime_translation.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("realtime_translation").manifest.output_schema


def _valid_input() -> dict:
    return {
        "audio_stream": "stream://call/73f2/audio-in",
        "source_lang": "en",
        "target_lang": "id",
    }


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_fields_raise_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(R.SkillInputError):
        await handle(
            {"audio_stream": "stream://x", "source_lang": "en"},
            ScriptedProvider(),
        )  # target_lang missing


@pytest.mark.asyncio
async def test_wrong_type_raises_input_error():
    bad = _valid_input()
    bad["source_lang"] = 42
    with pytest.raises(R.SkillInputError):
        await handle(bad, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Honest degraded result — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_not_available_result():
    out = await handle(_valid_input(), ScriptedProvider())
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    # No streaming translation infra: honest empty stream + zero latency.
    assert out["translated_stream"] == ""
    assert out["latency"] == 0.0


# ---------------------------------------------------------------------------
# 3. Full executor path — degraded result passes registry validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "realtime_translation", _valid_input(), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    assert out["translated_stream"] == ""
    assert out["latency"] == 0.0


# ---------------------------------------------------------------------------
# 4. Graceful degradation NEVER touches the provider (nothing to fabricate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_infra_does_not_raise_or_call_llm():
    provider = ScriptedProvider(fail=True)  # would raise if ever called
    out = await handle(_valid_input(), provider)
    assert provider.calls == []  # no LLM involved in honest degradation
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
