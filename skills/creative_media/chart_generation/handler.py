"""
Skill: chart_generation
=======================

Generate matplotlib code for a bar, line, pie, scatter, or heatmap chart from
tabular data. Returns the rendering code (``chart_code``) and the workspace
path of the produced image (``image_path``).

Permissions used:
  * ``filesystem:workspace:write`` and ``terminal:execute`` — declared by the
    manifest; this handler deliberately does NOT execute the generated code.
    Executing arbitrary model-written code by default would be unsafe, so no
    chart image is produced here.

Honesty note: ``chart_code`` is genuinely LLM-generated — the handler embeds
the *actual* data rows, chart type, title, and options in the prompt and
returns the model's reply verbatim (only trimmed). Because the code is never
executed, ``image_path`` is honestly returned as the empty string: the
matplotlib code is real and runnable by the caller, but no image file is
fabricated. If the model produces an empty reply, ``SkillOutputError`` is
raised rather than inventing chart code.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from typing import Any, List

from skills._common import (
    as_list,
    ask_llm_json,  # noqa: F401  (JSON variant unused here; text seam is chat_text)
    coerce_number,  # noqa: F401  (standard batch-import surface)
    coerce_str,  # noqa: F401  (standard batch-import surface)
    require,
)
from skills._llm import chat_text
from skills.registry import SkillInputError, SkillOutputError

__all__ = ["handle"]

_CHART_TYPES = ("bar", "line", "pie", "scatter", "heatmap")

SYSTEM = (
    "You are Forge's chart-generation engine. You are given REAL tabular data "
    "(as JSON rows), a chart type (bar | line | pie | scatter | heatmap), a "
    "title, and optional rendering options. Emit ONLY valid, self-contained "
    "Python matplotlib code that plots EXACTLY the data given — embed the "
    "real data values in the code, set the real title, and end by saving the "
    "figure to a file (e.g. plt.savefig('chart.png')). No prose, no "
    "explanation, no markdown code fences. Never invent data points that are "
    "not in the provided rows."
)


def _summarise_data(data: List[Any]) -> str:
    """Serialise the real data rows for the prompt (JSON, compact)."""
    try:
        return json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError):
        return str(data)


async def handle(input_data: dict, provider) -> dict:
    """Generate matplotlib chart code from real tabular data."""
    raw_data = require(input_data, "data", list, "the data rows to plot")
    rows = as_list(raw_data)
    if not rows:
        raise SkillInputError("field 'data' must contain at least one row")

    chart_type = require(input_data, "chart_type", str, "the chart type")
    if chart_type not in _CHART_TYPES:
        raise SkillInputError(
            f"chart_type must be one of {sorted(_CHART_TYPES)}, got {chart_type!r}"
        )

    title = require(input_data, "title", str, "the chart title")
    if not title.strip():
        raise SkillInputError("field 'title' must not be empty")

    options = input_data.get("options")
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise SkillInputError(
            f"field 'options' must be dict, got {type(options).__name__}"
        )

    data_blob = _summarise_data(rows)
    options_blob = _summarise_data([options])
    options_text = options_blob.strip()[1:-1].strip() or "(none)"

    prompt = (
        f"CHART TYPE: {chart_type}\n"
        f"TITLE: {title}\n"
        f"OPTIONS: {options_text}\n\n"
        f"DATA (verbatim, as JSON rows — plot EXACTLY these values):\n"
        f"-----\n{data_blob}\n-----\n\n"
        f"Write self-contained Python matplotlib code for a {chart_type} "
        f"chart titled {title!r} that plots the data rows above. Embed the "
        "real values in the code and save the figure with plt.savefig(). "
        "Output ONLY the Python code — no fences, no commentary."
    )

    code = await chat_text(provider, prompt, system=SYSTEM)
    chart_code = code.strip()
    if not chart_code:
        # The model gave us nothing usable. Refuse to fabricate chart code.
        raise SkillOutputError(
            "chart_generation: model reply contained no usable chart code"
        )

    return {
        "chart_code": chart_code,
        # Honest: the code is deliberately NOT executed (arbitrary code
        # execution is unsafe by default), so no image exists and no path is
        # fabricated. The caller may run chart_code themselves to produce it.
        "image_path": "",
    }
