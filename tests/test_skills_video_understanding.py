"""
Tests for the ``video_understanding`` skill handler.

No video-understanding backend is configured, so the handler is an honest
graceful stub: it validates inputs for real and returns empty ``summary`` /
``scenes`` / ``transcript`` rather than fabricating content for a video that
was never processed.

Honesty invariant under test: no summary, scene breakdown, or transcript is
ever invented — the stubbed output is schema-valid and clearly represents
"nothing understood".
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.video_understanding.handler import handle
from tests._skill_helpers import ScriptedProvider  # provider unused; kept for interface parity

QUESTIONS = ["What are the main announcements?", "How long is the demo section?"]


def _manifest():
    return skills.get_skill("video_understanding").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_video_source_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({"questions": QUESTIONS}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_questions_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({"video_url": "https://example.com/talk.mp4"}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Honest stub output — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_stub_output_schema_url():
    out = await handle(
        {"video_url": "https://example.com/talk.mp4", "questions": QUESTIONS},
        ScriptedProvider(),
    )

    assert R.validate_schema(_manifest().output_schema, out) == []
    # Honest: no backend processed the video, so nothing was understood.
    assert out["summary"] == ""
    assert out["scenes"] == []
    assert out["transcript"] == ""


@pytest.mark.asyncio
async def test_honest_stub_output_schema_path():
    out = await handle(
        {"video_path": "media/talk.mp4", "questions": QUESTIONS},
        ScriptedProvider(),
    )
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["summary"] == ""
    assert out["scenes"] == []


# ---------------------------------------------------------------------------
# 3. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "video_understanding",
        {"video_url": "https://example.com/talk.mp4", "questions": QUESTIONS},
        ScriptedProvider(),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["scenes"] == []
