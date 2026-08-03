"""
Tests for the ``image_generation`` skill handler.

No image-generation backend (DALL-E / Stable Diffusion) is configured, so
the handler is an honest graceful stub: it validates inputs for real and
returns an empty ``images`` array with ``generation_time == 0.0`` rather than
fabricating fake image URLs or files.

Honesty invariant under test: no artifact URL/path is ever invented — the
stubbed output is schema-valid and clearly represents "nothing generated".
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.image_generation.handler import handle
from tests._skill_helpers import ScriptedProvider  # provider unused; kept for interface parity

GOOD_INPUT = {
    "prompt": "isometric illustration of a self-hosted AI agent dashboard",
    "size": "512x512",
    "style": "flat vector",
    "n": 2,
}


def _manifest():
    return skills.get_skill("image_generation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_prompt_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle({"size": "512x512"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_bad_size_raises_input_error():
    with pytest.raises(R.SkillInputError, match="size"):
        await handle(
            {"prompt": "a cat", "size": "2048x2048"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_out_of_range_n_raises_input_error():
    with pytest.raises(R.SkillInputError, match="'n'"):
        await handle({"prompt": "a cat", "size": "512x512", "n": 0}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Honest stub output — schema-valid, nothing fabricated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_honest_stub_output_schema():
    out = await handle(GOOD_INPUT, ScriptedProvider())

    assert R.validate_schema(_manifest().output_schema, out) == []
    # Honest: no backend ran, so no images and zero generation time.
    assert out["images"] == []
    assert out["generation_time"] == 0.0


# ---------------------------------------------------------------------------
# 3. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "image_generation", dict(GOOD_INPUT), ScriptedProvider()
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["images"] == []
    assert out["generation_time"] == 0.0
