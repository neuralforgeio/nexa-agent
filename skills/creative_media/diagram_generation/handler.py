"""
Skill: diagram_generation
=========================

Generate a Mermaid, PlantUML, or SVG diagram from a natural-language
description. Returns the diagram source code (``diagram_code``) and an
optional rendered URL (``rendered_url``).

Permissions used:
  * ``filesystem:workspace:write`` — declared by the manifest; this handler
    does not itself write files (rendering/persisting diagrams is left to the
    caller, who receives the diagram source).

Honesty note: ``diagram_code`` is genuinely LLM-generated — the handler
embeds the *actual* user description, diagram type, and output format in the
prompt and returns the model's reply verbatim (only trimmed). There is no
local renderer wired up, so ``rendered_url`` is honestly returned as the
empty string: the code is real, but we do not render or host it. If the
model produces an empty reply, ``SkillOutputError`` is raised rather than
fabricating diagram code.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from skills._common import (
    as_list,  # noqa: F401  (standard batch-import surface)
    ask_llm_json,  # noqa: F401  (JSON variant unused here; text seam is chat_text)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,  # noqa: F401  (standard batch-import surface)
    require,
)
from skills._llm import chat_text
from skills.registry import SkillInputError, SkillOutputError

__all__ = ["handle"]

_DIAGRAM_TYPES = ("flowchart", "sequence", "erd", "architecture", "class")
_FORMATS = ("mermaid", "plantuml", "svg")

SYSTEM = (
    "You are Nexa's diagram-generation engine. You are given a REAL "
    "natural-language description of a system or process, a diagram type "
    "(flowchart | sequence | erd | architecture | class), and an output "
    "format (mermaid | plantuml | svg). Emit ONLY valid diagram source code "
    "in the requested format that faithfully represents the description "
    "given — no prose, no explanation, no markdown code fences, just the "
    "diagram source itself. Never invent entities or steps that the "
    "description does not mention or imply."
)


async def handle(input_data: dict, provider) -> dict:
    """Generate diagram source code from a natural-language description."""
    description = require(input_data, "description", str, "description of the diagram")
    if not description.strip():
        raise SkillInputError("field 'description' must not be empty")

    diagram_type = require(input_data, "diagram_type", str, "the diagram type")
    if diagram_type not in _DIAGRAM_TYPES:
        raise SkillInputError(
            f"diagram_type must be one of {sorted(_DIAGRAM_TYPES)}, got {diagram_type!r}"
        )

    fmt = require(input_data, "format", str, "the output format")
    if fmt not in _FORMATS:
        raise SkillInputError(
            f"format must be one of {sorted(_FORMATS)}, got {fmt!r}"
        )

    prompt = (
        f"DIAGRAM TYPE: {diagram_type}\n"
        f"OUTPUT FORMAT: {fmt}\n\n"
        f"DESCRIPTION (verbatim, from the user):\n"
        f"-----\n{description}\n-----\n\n"
        f"Write a {diagram_type} diagram in {fmt} that represents EXACTLY the "
        "description above. Output ONLY the diagram source code — no fences, "
        "no commentary."
    )

    code = await chat_text(provider, prompt, system=SYSTEM)
    diagram_code = code.strip()
    if not diagram_code:
        # The model gave us nothing usable. Refuse to fabricate a diagram.
        raise SkillOutputError(
            "diagram_generation: model reply contained no usable diagram code"
        )

    return {
        "diagram_code": diagram_code,
        # Honest: no local renderer/hosting is configured, so nothing has
        # been rendered — the caller gets the source, not a URL.
        "rendered_url": "",
    }
