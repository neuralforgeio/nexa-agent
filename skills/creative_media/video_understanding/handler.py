"""
Skill: video_understanding
==========================

Understand a video from a workspace path or URL: answer questions, produce a
scene-by-scene breakdown, and return a spoken-word transcript. Returns
``summary``, ``scenes``, and ``transcript``.

Permissions used:
  * ``filesystem:workspace`` — declared by the manifest; no file is read by
    this stub (there is no video backend to feed frames/audio to).
  * ``network:*`` — declared by the manifest for the ``video_url`` variant;
    nothing is fetched by this handler.

Honesty note (critical): there is NO video-understanding backend wired up in
this project. Rather than fabricating a summary, scenes, or a transcript for
a video that was never processed, this handler honestly returns empty values
(``summary=""``, ``scenes=[]``, ``transcript=""``) — a schema-valid result
that clearly represents "nothing was understood". No visual or audio content
is invented.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from skills._common import (
    as_list,
    ask_llm_json,  # noqa: F401  (standard batch-import surface)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,
    require,
)
from skills.registry import SkillInputError

__all__ = ["handle"]


def _questions(data: Dict[str, Any]) -> List[str]:
    """Extract the required non-empty list of question strings."""
    raw = require(data, "questions", list, "questions to answer about the video")
    items = as_list(raw)
    if not items:
        raise SkillInputError("field 'questions' must contain at least one question")
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            raise SkillInputError(
                f"field 'questions' entries must be str, got {type(item).__name__}"
            )
        if item.strip():
            out.append(item)
    if not out:
        raise SkillInputError("field 'questions' must contain at least one question")
    return out


async def handle(input_data: dict, provider) -> dict:
    """Understand a video (honest stub: no video backend configured)."""
    video_path = coerce_str(input_data.get("video_path")).strip()
    video_url = coerce_str(input_data.get("video_url")).strip()
    if not video_path and not video_url:
        raise SkillInputError(
            "either 'video_path' or 'video_url' must be provided"
        )

    _questions(input_data)

    # Graceful stub: no video-understanding backend is configured, so nothing
    # is summarised, no scenes are detected, and no transcript is produced.
    # Return an honest, schema-valid empty result instead of fabricated
    # content.
    return {
        "summary": "",
        "scenes": [],
        "transcript": "",
    }
