"""
Skill: image_generation
=======================

Generate one or more images from a text prompt with a chosen size and
optional style. Returns image references (``images``) plus the wall-clock
generation time (``generation_time``).

Permissions used:
  * ``network:*`` and ``filesystem:workspace:write`` — declared by the
    manifest; this handler performs no network calls and writes no files,
    because no image-generation backend is configured.

Honesty note (graceful stub): image generation requires an external backend
such as DALL-E or Stable Diffusion, and none is configured in this project.
Rather than fabricating fake image URLs or files, this handler honestly
returns an empty ``images`` array and a ``generation_time`` of 0.0 — a
schema-valid result that clearly represents "nothing was generated". No
network call is made and no artifact path is invented.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from skills._common import (
    as_list,  # noqa: F401  (standard batch-import surface)
    ask_llm_json,  # noqa: F401  (standard batch-import surface)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,
    require,
)
from skills.registry import SkillInputError

__all__ = ["handle"]

_SIZES = ("256x256", "512x512", "1024x1024")


async def handle(input_data: dict, provider) -> dict:
    """Generate images from a prompt (honest stub: no backend configured)."""
    prompt = require(input_data, "prompt", str, "the text prompt")
    if not prompt.strip():
        raise SkillInputError("field 'prompt' must not be empty")

    size = require(input_data, "size", str, "the image size")
    if size not in _SIZES:
        raise SkillInputError(
            f"size must be one of {sorted(_SIZES)}, got {size!r}"
        )

    n_raw = input_data.get("n", 1)
    if isinstance(n_raw, bool) or not isinstance(n_raw, int):
        raise SkillInputError(
            f"field 'n' must be int, got {type(n_raw).__name__}"
        )
    if not 1 <= n_raw <= 10:
        raise SkillInputError(f"field 'n' must be between 1 and 10, got {n_raw}")

    coerce_str(input_data.get("style"), default="")  # parsed; unused without a backend

    # Graceful stub: no image-generation backend (DALL-E/Stable Diffusion) is
    # configured, so nothing is generated. Return a schema-valid, honest
    # result — empty images, zero time — instead of fabricated artifact URLs.
    return {
        "images": [],
        "generation_time": 0.0,
    }
