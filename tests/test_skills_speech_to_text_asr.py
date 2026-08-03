"""
Tests for the ``speech_to_text_asr`` skill (communication).

This skill is an HONEST graceful-degradation stub: no ASR backend (whisper
or otherwise) is bundled with this runtime, so the handler verifies the
audio file really exists in the workspace and then returns a schema-valid,
honestly-empty result — it never fabricates a transcript for audio it
cannot decode, and it never raises just because no backend exists.

The workspace file check runs for real against a temporary workspace
(``NEXA_WORKSPACE`` pointed at ``tmp_path``).

Note: pytest-asyncio runs in STRICT mode in this repo, so every coroutine
test is explicitly decorated with ``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.communication.speech_to_text_asr.handler import handle
from tests._skill_helpers import ScriptedProvider


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "standup.mp3").write_bytes(b"\x00" * 16)
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # nexa.config.NEXA_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_file_tools_*).
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("speech_to_text_asr").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_audio_path_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle({"audio_path": "nope_missing.mp3"}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Honest degraded result — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_degraded_result_with_language_hint(ws):
    out = await handle(
        {"audio_path": "standup.mp3", "language": "en", "diarize": True},
        ScriptedProvider(),
    )
    assert R.validate_schema(_manifest().output_schema, out) == []
    # No ASR backend: transcript/segments are honestly empty, NOT invented.
    assert out["transcript"] == ""
    assert out["segments"] == []
    # The caller's language hint is echoed honestly.
    assert out["language"] == "en"


@pytest.mark.asyncio
async def test_language_defaults_to_unknown(ws):
    out = await handle({"audio_path": "standup.mp3"}, ScriptedProvider())
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["language"] == "unknown"


# ---------------------------------------------------------------------------
# 3. Full executor path — the degraded result passes registry validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "speech_to_text_asr",
        {"audio_path": "standup.mp3", "language": "id", "diarize": False},
        ScriptedProvider(),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["transcript"] == ""
    assert out["segments"] == []
    assert out["language"] == "id"


# ---------------------------------------------------------------------------
# 4. Graceful degradation NEVER touches the provider (nothing to hallucinate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_backend_does_not_raise_or_call_llm(ws):
    provider = ScriptedProvider(fail=True)  # would raise if ever called
    out = await handle({"audio_path": "standup.mp3"}, provider)
    assert provider.calls == []  # the model was never asked to fake a transcript
    assert R.validate_schema(_manifest().output_schema, out) == []
