"""
Tests for the ``voice_cloning`` skill handler.

No voice-cloning backend is configured, so the handler is an honest graceful
stub: it validates inputs for real, genuinely verifies the sample audio file
exists in the workspace (``FORGE_WORKSPACE`` pointed at ``tmp_path``), and
returns ``audio_path == ""`` with ``similarity_score == 0.0`` rather than
fabricating synthesized audio.

Honesty invariant under test: no audio artifact path is ever invented — the
stubbed output is schema-valid and clearly represents "nothing synthesized".
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.voice_cloning.handler import handle
from tests._skill_helpers import ScriptedProvider  # provider unused; kept for interface parity

GOOD_INPUT = {
    "sample_audio_path": "media/voice_sample.wav",
    "text": "Welcome back, your daily briefing is ready.",
    "language": "en",
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    (media / "voice_sample.wav").write_bytes(b"RIFF fake-but-present")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # FORGE_WORKSPACE is captured at import time by tools._paths, so the env
    # var alone is not enough — repoint the already-imported reference.
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("voice_cloning").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_sample_audio_path_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"text": "hello"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_text_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle(
            {"sample_audio_path": "media/voice_sample.wav"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_missing_sample_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"sample_audio_path": "media/nope.wav", "text": "hello"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Honest stub output — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_stub_output_schema(ws):
    out = await handle(dict(GOOD_INPUT), ScriptedProvider())

    assert R.validate_schema(_manifest().output_schema, out) == []
    # Honest: no clone backend ran, so no audio exists and similarity is 0.
    assert out["audio_path"] == ""
    assert out["similarity_score"] == 0.0


# ---------------------------------------------------------------------------
# 3. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "voice_cloning", dict(GOOD_INPUT), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["audio_path"] == ""
    assert out["similarity_score"] == 0.0
