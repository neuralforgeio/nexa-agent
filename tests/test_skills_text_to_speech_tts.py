"""
Tests for the ``text_to_speech_tts`` skill (communication).

This skill is an HONEST graceful-degradation stub: no TTS backend (Piper,
Coqui, cloud speech, ...) is bundled with this runtime, so the handler
returns a schema-valid, honestly "not synthesized" result — ``audio_path``
is empty (no audio artifact is written or claimed), ``duration`` is 0.0,
and ``metadata`` states exactly why. It never fabricates an audio file and
never raises just because no backend exists.

Note: pytest-asyncio runs in STRICT mode in this repo, so every coroutine
test is explicitly decorated with ``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.communication.text_to_speech_tts.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("text_to_speech_tts").manifest.output_schema


def _valid_input() -> dict:
    return {
        "text": "Your build finished successfully.",
        "voice": "neutral",
        "speed": 1.0,
        "language": "en",
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
            {"text": "hi", "voice": "neutral"}, ScriptedProvider()
        )  # language missing


@pytest.mark.asyncio
async def test_invalid_voice_and_speed_raise_input_error():
    bad_voice = _valid_input()
    bad_voice["voice"] = "robotic"
    with pytest.raises(R.SkillInputError):
        await handle(bad_voice, ScriptedProvider())

    bad_speed = _valid_input()
    bad_speed["speed"] = "fast"
    with pytest.raises(R.SkillInputError):
        await handle(bad_speed, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Honest degraded result — schema-valid, no fabricated artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_not_synthesized_result():
    out = await handle(_valid_input(), ScriptedProvider())

    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    # Nothing was synthesized — and the handler says so, honestly.
    assert out["audio_path"] == ""
    assert out["duration"] == 0.0
    assert out["metadata"]["synthesized"] is False
    assert out["metadata"]["reason"] == "no TTS backend configured"
    # The request parameters are echoed for the caller's records.
    assert out["metadata"]["voice"] == "neutral"
    assert out["metadata"]["language"] == "en"
    assert out["metadata"]["speed"] == 1.0


@pytest.mark.asyncio
async def test_speed_default_applies():
    payload = _valid_input()
    del payload["speed"]  # input_schema default: 1.0
    out = await handle(payload, ScriptedProvider())
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    assert out["metadata"]["speed"] == 1.0
    assert out["audio_path"] == ""


# ---------------------------------------------------------------------------
# 3. Full executor path — degraded result passes registry validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "text_to_speech_tts", _valid_input(), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
    assert out["metadata"]["synthesized"] is False
    assert out["audio_path"] == ""


# ---------------------------------------------------------------------------
# 4. Graceful degradation NEVER touches the provider (nothing to fabricate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_backend_does_not_raise_or_call_llm():
    provider = ScriptedProvider(fail=True)  # would raise if ever called
    out = await handle(_valid_input(), provider)
    assert provider.calls == []  # no LLM involved in honest degradation
    assert R.validate_schema(OUTPUT_SCHEMA, out) == []
