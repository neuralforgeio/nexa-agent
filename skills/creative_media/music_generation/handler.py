"""
Skill: music_generation
=======================

Generate a short music track from a prompt with a target duration and
optional genre and mood. Returns the workspace path of the audio file
(``audio_path``) plus generation ``metadata``.

Permissions used:
  * ``network:*`` and ``filesystem:workspace:write`` — declared by the
    manifest; this handler performs no network calls and writes no files,
    because no music-generation backend is configured.

Honesty note (graceful stub): music generation requires an external audio
backend (e.g. a music-diffusion service), and none is configured in this
project. Rather than fabricating a path to an audio file that does not
exist, this handler honestly returns ``audio_path=""`` and
``metadata={"generated": false, "reason": "no music backend configured"}`` —
a schema-valid result that clearly represents "nothing was generated".

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


async def handle(input_data: dict, provider) -> dict:
    """Generate music from a prompt (honest stub: no backend configured)."""
    prompt = require(input_data, "prompt", str, "the text prompt")
    if not prompt.strip():
        raise SkillInputError("field 'prompt' must not be empty")

    duration = require(input_data, "duration", int, "target duration in seconds")
    if not 1 <= duration <= 600:
        raise SkillInputError(
            f"field 'duration' must be between 1 and 600, got {duration}"
        )

    coerce_str(input_data.get("genre"), default="")  # parsed; unused without a backend
    coerce_str(input_data.get("mood"), default="")  # parsed; unused without a backend

    # Graceful stub: no music-generation backend is configured, so nothing is
    # generated and no file is written. Return a schema-valid, honest result
    # instead of a fabricated audio path.
    return {
        "audio_path": "",
        "metadata": {"generated": False, "reason": "no music backend configured"},
    }
