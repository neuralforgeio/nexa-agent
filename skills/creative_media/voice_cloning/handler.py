"""
Skill: voice_cloning
====================

Clone a voice from a sample audio file and synthesize new text in that voice.
Returns the workspace path of the synthesized audio (``audio_path``) plus a
voice similarity score (``similarity_score``).

Permissions used:
  * ``filesystem:workspace`` — ``sample_audio_path`` is resolved through
    :func:`agent.tool_api.workspace_path` (sandboxed to ``NEXA_WORKSPACE``)
    and checked for real existence on disk.
  * ``network:*`` — declared by the manifest; nothing is fetched by this
    handler.

Honesty note (graceful stub): voice cloning requires an external TTS/voice
backend, and none is configured in this project. Rather than fabricating a
synthesized audio file, this handler honestly returns ``audio_path=""`` and
``similarity_score=0.0`` — a schema-valid result that clearly represents
"nothing was synthesized". The sample file itself IS genuinely verified to
exist when given, so path-validation errors are real.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from skills._common import (
    as_list,  # noqa: F401  (standard batch-import surface)
    ask_llm_json,  # noqa: F401  (standard batch-import surface)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,
    require,
)
from agent import tool_api
from skills.registry import SkillInputError

__all__ = ["handle"]


def _confirm_workspace_file(rel_path: str) -> None:
    """Resolve ``rel_path`` in the workspace and require it to exist."""
    try:
        p = tool_api.workspace_path(rel_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid sample_audio_path {rel_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"sample audio file {rel_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )


async def handle(input_data: dict, provider) -> dict:
    """Clone a voice from a sample (honest stub: no clone backend configured)."""
    sample = require(input_data, "sample_audio_path", str, "the voice sample audio file")
    if not sample.strip():
        raise SkillInputError("field 'sample_audio_path' must not be empty")

    text = require(input_data, "text", str, "the text to synthesize")
    if not text.strip():
        raise SkillInputError("field 'text' must not be empty")

    coerce_str(input_data.get("language"), default="en")  # parsed; unused without a backend

    # Genuinely verify the sample audio file exists in the workspace.
    _confirm_workspace_file(sample)

    # Graceful stub: no voice-cloning backend is configured, so nothing is
    # synthesized. Return a schema-valid, honest result instead of a
    # fabricated audio path.
    return {
        "audio_path": "",
        "similarity_score": 0.0,
    }
