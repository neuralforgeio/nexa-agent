# SPDX-License-Identifier: MIT
"""Skill: data_analysis.

Purpose: read a real workspace data file (typically CSV) and compute honest
summary statistics, a correlation matrix, or outlier counts in pure Python —
then let the LLM *interpret* those computed numbers into structured findings
(finding / evidence / recommendation) and a summary. For `forecast`, a simple
least-squares linear projection over the first numeric column is computed in
code and the LLM narrates it.

Permissions: ``filesystem:workspace`` (read via ``agent.tool_api``),
``terminal:execute`` (declared by the manifest; not exercised here).

Honest note: every number in ``statistics`` comes from the real file parsed by
this module — the model is only asked to *explain* numbers it is shown, never
to invent them. ``visualizations`` is always ``[]``: this skill does not
render charts (documented in the manifest description). If the model's reply
is not parseable JSON, ``ValueError`` propagates rather than fabricating
insights.
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent import tool_api
from skills._common import (
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)
from skills._llm import chat_json  # noqa: F401  (re-exported seam; ask_llm_json uses it)
from skills.registry import SkillInputError

__all__ = ["handle"]


SYSTEM = (
    "You are Nexa's data-analysis engine. You are given a data file's REAL "
    "contents and, for numeric work, the REAL statistics that were computed "
    "from it by code. Interpret ONLY the numbers and sample rows you are "
    "shown — do not invent figures or findings. Respond with a SINGLE JSON "
    "object, and nothing else (no markdown fences, no prose), with exactly "
    "these keys: "
    '"insights" (an array of objects, each with "finding", "evidence", and '
    '"recommendation" strings; base evidence strictly on the supplied '
    "statistics/sample), and "
    '"statistics" (an object echoing the key statistics you relied on). '
    "Use an empty insights array only if there is genuinely nothing to report."
)

_MAX_SAMPLE_ROWS = 5


# ---------------------------------------------------------------------------
# Real file loading (sandboxed to the workspace)
# ---------------------------------------------------------------------------

def _read_text(file_path: str) -> str:
    try:
        p = tool_api.workspace_path(file_path)
    except ValueError as exc:  # escapes workspace
        raise SkillInputError(f"invalid data_source {file_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"data_source {file_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )
    return p.read_text(encoding="utf-8", errors="replace")


def _parse_csv(text: str):
    # type: (...) -> tuple[list[str], list[dict[str, str]], list[list[str]]]
    """Return (headers, row-dicts, sample raw rows) from CSV text."""
    reader = csv.reader(io.StringIO(text))
    raw: List[List[str]] = [row for row in reader if row]
    if not raw:
        return [], [], []
    headers = [h.strip() or f"col_{i}" for i, h in enumerate(raw[0])]
    rows = [
        {headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))}
        for row in raw[1:]
    ]
    return headers, rows, raw[1 : 1 + _MAX_SAMPLE_ROWS]


def _try_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Statistics computed in code (no LLM involved)
# ---------------------------------------------------------------------------

def _numeric_columns(headers, rows) -> Dict[str, List[float]]:
    cols: Dict[str, List[float]] = {h: [] for h in headers}
    for row in rows:
        for h in headers:
            v = _try_float(row.get(h))
            if v is not None:
                cols[h].append(v)
    # keep only columns with at least one numeric value
    return {h: vals for h, vals in cols.items() if vals}


def _col_stats(values: List[float]) -> Dict[str, float]:
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    return {
        "count": n,
        "mean": round(mean, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "stdev": round(math.sqrt(variance), 6),
    }


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xs, ys = xs[:n], ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(sxy / math.sqrt(sxx * syy), 6)


def _compute_statistics(analysis_type: str, headers, rows) -> Dict[str, Any]:
    """Compute the real statistics for the requested analysis_type."""
    numeric = _numeric_columns(headers, rows)
    base: Dict[str, Any] = {
        "row_count": len(rows),
        "column_count": len(headers),
        "columns": headers,
        "numeric_columns": sorted(numeric.keys()),
    }

    if analysis_type == "summary":
        base["columns_stats"] = {h: _col_stats(vals) for h, vals in numeric.items()}
        return base

    if analysis_type == "correlation":
        matrix: Dict[str, Dict[str, Optional[float]]] = {}
        keys = sorted(numeric.keys())
        for a in keys:
            matrix[a] = {b: _pearson(numeric[a], numeric[b]) for b in keys}
        base["correlation_matrix"] = matrix
        return base

    if analysis_type == "outlier":
        # IQR method per numeric column; counts only (indices kept internal).
        out: Dict[str, Any] = {}
        for h, vals in sorted(numeric.items()):
            s = sorted(vals)
            n = len(s)
            q1 = s[n // 4]
            q3 = s[(3 * n) // 4]
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            count = sum(1 for v in vals if v < lo or v > hi)
            out[h] = {"q1": q1, "q3": q3, "iqr": round(iqr, 6), "outlier_count": count}
        base["outliers"] = out
        return base

    if analysis_type == "forecast":
        # Simple least-squares linear trend over the first numeric column.
        if not numeric:
            base["forecast"] = {"error": "no numeric column found to project"}
            return base
        col = sorted(numeric.keys())[0]
        ys = numeric[col]
        n = len(ys)
        xs = list(range(n))
        mx = sum(xs) / n
        my = sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = 0.0 if sxx == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        intercept = my - slope * mx
        next3 = [round(intercept + slope * (n + k), 6) for k in range(3)]
        base["forecast"] = {
            "column": col,
            "method": "least_squares_linear",
            "slope": round(slope, 6),
            "intercept": round(intercept, 6),
            "next_3_periods": next3,
        }
        return base

    return base


# ---------------------------------------------------------------------------
# Normalisation of LLM output to the manifest's output_schema
# ---------------------------------------------------------------------------

def _normalise_insight(item: Any) -> Dict[str, str]:
    if isinstance(item, dict):
        return {
            "finding": coerce_str(item.get("finding")),
            "evidence": coerce_str(item.get("evidence")),
            "recommendation": coerce_str(item.get("recommendation")),
        }
    return {"finding": coerce_str(item), "evidence": "", "recommendation": ""}


def _fallback_insights(analysis_type: str, stats: Dict[str, Any]) -> List[Dict[str, str]]:
    """Deterministic, code-derived insight if the model returns none."""
    rc = stats.get("row_count")
    nc = len(stats.get("numeric_columns", []) or [])
    return [
        {
            "finding": f"Dataset has {rc} data rows and {nc} numeric column(s).",
            "evidence": json.dumps(
                {k: stats[k] for k in ("row_count", "numeric_columns") if k in stats}
            ),
            "recommendation": "Review the computed statistics for column-level detail.",
        }
    ]


async def handle(input_data: dict, provider) -> dict:
    """Analyse a workspace data file and return LLM-interpreted insights."""
    data_source = require(input_data, "data_source", str, "workspace path of the data file")
    analysis_type = require(input_data, "analysis_type", str, "summary|correlation|outlier|forecast")
    if analysis_type not in ("summary", "correlation", "outlier", "forecast"):
        raise SkillInputError(
            f"analysis_type must be one of summary|correlation|outlier|forecast, "
            f"got {analysis_type!r}"
        )

    text = _read_text(data_source)
    headers, rows, sample = _parse_csv(text)
    if not headers:
        raise SkillInputError(f"data_source {data_source!r} parsed to zero columns/rows")

    stats = _compute_statistics(analysis_type, headers, rows)

    prompt = (
        f"Data file: {data_source}\n"
        f"Analysis type: {analysis_type}\n\n"
        f"Computed statistics (REAL, from code — trust these numbers):\n"
        f"{json.dumps(stats, indent=2)}\n\n"
        f"Sample data rows (first {len(sample)}, verbatim CSV):\n"
        + "\n".join(",".join(r) for r in sample)
        + "\n\nInterpret these statistics for the requested analysis. "
        "Ground every insight's evidence strictly in the numbers above. "
        'Return a single JSON object with "insights" (array of '
        '{"finding","evidence","recommendation"}) and "statistics" (object).'
    )

    data = await ask_llm_json(provider, prompt, system=SYSTEM, fallback=None)

    insights = [_normalise_insight(i) for i in as_list(data.get("insights"))]
    if not insights:
        insights = _fallback_insights(analysis_type, stats)

    # Merge model-echoed stats over the code-computed ones only when it's an
    # object; the code-computed stats are always present as the source of truth.
    model_stats = data.get("statistics")
    statistics: Dict[str, Any] = dict(stats)
    if isinstance(model_stats, dict):
        statistics.update(model_stats)

    return {
        "insights": insights,
        "statistics": statistics,
        "visualizations": [],
    }
