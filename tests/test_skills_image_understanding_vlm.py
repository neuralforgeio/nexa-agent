"""
Tests for the ``image_understanding_vlm`` skill handler.

There is no local vision-language model backend, so the handler returns an
honest degraded result: per-question answers that state plainly that a vision
backend is not configured (``confidence`` 0.0), empty ``detected_objects``
and ``extracted_text``. What DOES run for real is the workspace path
validation (``NEXA_WORKSPACE`` pointed at ``tmp_path``) and schema
validation.

Honesty invariant under test: no visual content is ever fabricated — answers
describe the missing backend, not the image.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.image_understanding_vlm.handler import handle
from tests._skill_helpers import ScriptedProvider  # provider unused; kept for interface parity

QUESTIONS = ["What components does this diagram show?", "Is there any text?"]


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "diagram.png").write_bytes(b"\x89PNG fake-but-present")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # NEXA_WORKSPACE is captured at import time by tools._paths, so the env
    # var alone is not enough — repoint the already-imported reference.
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("image_understanding_vlm").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_image_source_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"questions": QUESTIONS}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_questions_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({"image_url": "https://example.com/arch.png"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_image_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"image_path": "nope_missing.png", "questions": QUESTIONS},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Honest degraded output — schema-valid, nothing visual fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_degraded_output_with_real_file(ws):
    out = await handle(
        {"image_path": "diagram.png", "questions": QUESTIONS}, ScriptedProvider()
    )

    assert R.validate_schema(_manifest().output_schema, out) == []

    assert len(out["answers"]) == len(QUESTIONS)
    for item, q in zip(out["answers"], QUESTIONS):
        assert item["question"] == q
        assert "vision backend" in item["answer"]
        assert item["confidence"] == 0.0
    # No VLM ran, so nothing was detected or extracted — honestly empty.
    assert out["detected_objects"] == []
    assert out["extracted_text"] == ""


@pytest.mark.asyncio
async def test_honest_degraded_output_with_url(ws):
    out = await handle(
        {"image_url": "https://example.com/arch.png", "questions": QUESTIONS[:1]},
        ScriptedProvider(),
    )
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["answers"][0]["confidence"] == 0.0
    assert out["detected_objects"] == []


# ---------------------------------------------------------------------------
# 3. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "image_understanding_vlm",
        {"image_path": "diagram.png", "questions": QUESTIONS},
        ScriptedProvider(),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert all(a["confidence"] == 0.0 for a in out["answers"])
