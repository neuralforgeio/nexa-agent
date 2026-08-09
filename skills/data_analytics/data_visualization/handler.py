# SPDX-License-Identifier: MIT
"""Skill: data_visualization.

Purpose: design a dashboard, chart, or report visualization for a supplied
dataset. The LLM proposes the component list and a human-readable description
grounded in the real data (which is embedded in the prompt); code supplies
deterministic fallback components when the model returns none.

Permissions: ``filesystem:workspace:write``, ``terminal:execute`` (both declared
by the manifest; neither is exercised — no file is rendered here).

Honest note: ``dashboard_path`` is always ``""`` because this skill does NOT
render or write any actual dashboard file (documented in the manifest
description). ``components`` and ``description`` come from the model's reply
about the real data, with a deterministic code-computed fallback for
``components`` if the model leaves it empty. The summary stats shown to the
model are computed in code from the real ``data``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from skills._common import (
    as_list,
    ask_llm_json,
    coerce_number,  # noqa: F401  (kept import surface aligned with batch kit)
    coerce_str,
    require,
)
from skills._llm import chat_json  # noqa: F401  (re-exported seam; ask_llm_json uses it)
from skills.registry import SkillInputError

__all__ = ["handle"]

_SYSTEM = (
    "You are Forge's data-visualization designer. You are given the REAL "
    "dataset (as JSON rows), a requested visualization type "
    "(dashboard|chart|report), an optional layout hint, and some code-computed "
    "summary statistics. Propose ONLY components that make sense for the data "
    "actually shown. Respond with a SINGLE JSON object, and nothing else (no "
    "markdown fences, no prose), with exactly these keys: "
    '"components" (an array of short strings naming the dashboard/report/'
    "chart components, e.g. \"line chart: signups over time\"), and "
    '"description" (a one-paragraph human-readable description of the '
    "designed visualization). Do not claim any file was rendered."
)


def _summarise_data(data: List[Any]) -> Dict[str, Any]:
    """Compute real summary stats over the dataset for the prompt."""
    numeric_keys: Dict[str, List[float]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                numeric_keys.setdefault(str(k), []).append(float(v))
            elif isinstance(v, str):
                try:
                    numeric_keys.setdefault(str(k), []).append(float(v))
                except ValueError:
                    pass
    stats: Dict[str, Any] = {
        "row_count": len(data),
        "numeric_columns": sorted(k for k, v in numeric_keys.items() if v),
    }
    col_stats = {}
    for k, vals in numeric_keys.items():
        if not vals:
            continue  # never divide by zero on a non-numeric column
        n = len(vals)
        mean = sum(vals) / n
        col_stats[k] = {
            "count": n,
            "mean": round(mean, 6),
            "min": round(min(vals), 6),
            "max": round(max(vals), 6),
        }
    if col_stats:
        stats["column_stats"] = col_stats
    return stats


def _fallback_components(viz_type: str, data: List[Any], stats: Dict[str, Any]) -> List[str]:
    """Deterministic components derived from the real data shape."""
    numeric = stats.get("numeric_columns") or []
    cols = ", ".join(numeric) if numeric else "no numeric columns"
    base = [
        f"{viz_type} header: {stats.get('row_count', 0)} data rows",
        f"summary table of numeric columns ({cols})",
    ]
    if viz_type in ("dashboard", "chart") and numeric:
        base.append(f"primary chart plotting {numeric[0]}")
    if viz_type == "report":
        base.append("narrative section summarising the column statistics")
    return base


async def handle(input_data: dict, provider) -> dict:
    """Design a visualization for the real dataset; no rendering performed."""
    data = require(input_data, "data", list, "the dataset to visualize")
    viz_type = require(input_data, "viz_type", str, "dashboard|chart|report")
    if viz_type not in ("dashboard", "chart", "report"):
        raise SkillInputError(
            f"viz_type must be one of dashboard|chart|report, got {viz_type!r}"
        )
    layout = input_data.get("layout")
    if layout is not None and not isinstance(layout, dict):
        raise SkillInputError(f"layout must be an object, got {type(layout).__name__}")

    stats = _summarise_data(data)
    # Give the model the real data, capped so enormous inputs stay readable.
    sample = data[:25]

    prompt = (
        f"Visualization type: {viz_type}\n"
        f"Layout hint: {json.dumps(layout) if layout else '(none)'}\n\n"
        f"Code-computed summary of the dataset (REAL):\n"
        f"{json.dumps(stats, indent=2)}\n\n"
        f"Dataset (first {len(sample)} rows, REAL, as JSON):\n"
        f"{json.dumps(sample, indent=2, default=str)}\n\n"
        "Design the visualization for THIS data. Return a single JSON object "
        'with "components" (array of strings) and "description" (string).'
    )

    payload = await ask_llm_json(provider, prompt, system=_SYSTEM, fallback=None)

    components = [coerce_str(c) for c in as_list(payload.get("components")) if c is not None]
    components = [c for c in components if c]
    if not components:
        components = _fallback_components(viz_type, data, stats)

    description = coerce_str(payload.get("description"))
    if not description:
        description = (
            f"{viz_type} for {stats.get('row_count', 0)} rows covering numeric "
            f"columns: {', '.join(stats.get('numeric_columns') or []) or 'none'}."
        )

    return {
        "dashboard_path": "",
        "components": components,
        "description": description,
    }
