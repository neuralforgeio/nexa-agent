"""
Tests for the ``music_generation`` skill handler.

No music-generation backend is configured, so the handler is an honest
graceful stub: it validates inputs for real and returns ``audio_path == ""``
with ``metadata["generated"] is False`` rather than fabricating a path to an
audio file that does not exist.

Honesty invariant under test: no artifact path is ever invented — the stubbed
output is schema-valid and clearly represents "nothing generated".
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.music_generation.handler import handle
from tests._skill_helpers import ScriptedProvider  # provider unused; kept for interface parity

GOOD_INPUT = {
    "prompt": "lo-fi hip hop beat for deep focus",
    "duration": 60,
    "genre": "lofi",
    "mood": "calm",
}


def _manifest():
    return skills.get_skill("music_generation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_duration_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({"prompt": "lofi beat"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_out_of_range_duration_raises_input_error():
    with pytest.raises(R.SkillInputError, match="duration"):
        await handle(
            {"prompt": "lofi beat", "duration": 900}, ScriptedProvider()
        )


# ---------------------------------------------------------------------------
# 2. Honest stub output — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_stub_output_schema():
    out = await handle(GOOD_INPUT, ScriptedProvider())

    assert R.validate_schema(_manifest().output_schema, out) == []
    # Honest: no backend ran, so no audio file exists. The metadata
    # explicitly says the track was not generated.
    assert out["audio_path"] == ""
    assert out["metadata"]["generated"] is False
    assert "no music backend" in out["metadata"]["reason"]


# ---------------------------------------------------------------------------
# 3. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "music_generation", dict(GOOD_INPUT), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["audio_path"] == ""
    assert out["metadata"]["generated"] is False
