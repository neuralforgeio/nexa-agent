"""
Skill: image_understanding_vlm
==============================

Answer questions about an image supplied as a workspace path or URL using a
vision-language model. Returns per-question ``answers``, plus optional
``detected_objects`` and ``extracted_text`` (OCR).

Permissions used:
  * ``filesystem:workspace`` — when ``image_path`` is given it is resolved
    through :func:`agent.tool_api.workspace_path` (sandboxed to
    ``FORGE_WORKSPACE``) and checked for real existence on disk.
  * ``network:*`` — declared by the manifest for the ``image_url`` variant;
    nothing is fetched by this handler.

Honesty note (critical): there is NO vision-language model backend wired up
in this project — the provider boundary here is text-only and cannot see
pixels. Rather than fabricating visual content, this handler returns an
honest degraded result: every question's ``answer`` states plainly that image
understanding requires a vision backend (not configured), ``confidence`` is
0.0, and ``detected_objects`` / ``extracted_text`` are empty. The file IS
genuinely verified to exist when ``image_path`` is used, so path-validation
errors are real. Schema-valid always; honest always.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import (
    as_list,
    ask_llm_json,  # noqa: F401  (standard batch-import surface; no local VLM reply is asked of the text model)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,
    require,
)
from skills.registry import SkillInputError

__all__ = ["handle"]

_NO_VLM_NOTE = "image understanding requires a vision backend (not configured)"


def _confirm_workspace_file(rel_path: str) -> None:
    """Resolve ``rel_path`` in the workspace and require it to exist."""
    try:
        p = tool_api.workspace_path(rel_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid image_path {rel_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"image file {rel_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )


def _questions(data: Dict[str, Any]) -> List[str]:
    """Extract the required non-empty list of question strings."""
    raw = require(data, "questions", list, "questions to answer about the image")
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
    """Answer questions about an image (honest degraded: no VLM backend)."""
    image_path = coerce_str(input_data.get("image_path")).strip()
    image_url = coerce_str(input_data.get("image_url")).strip()
    if not image_path and not image_url:
        raise SkillInputError(
            "either 'image_path' or 'image_url' must be provided"
        )

    questions = _questions(input_data)

    if image_path:
        # Genuinely verify the referenced file exists in the workspace.
        _confirm_workspace_file(image_path)

    # No vision backend is configured: a text-only provider cannot answer
    # questions about pixels, so we return an honest per-question degraded
    # answer instead of fabricating visual content.
    answers = [
        {
            "question": q,
            "answer": _NO_VLM_NOTE,
            "confidence": 0.0,
        }
        for q in questions
    ]
    return {
        "answers": answers,
        "detected_objects": [],
        "extracted_text": "",
    }
