"""
OpenForge — trend_analysis skill (web_research)
================================================

Purpose
-------
Analyse a time series ``data`` (array of {timestamp, value}) for a named
``metric`` and forecast ``forecast_periods`` steps ahead (default 7). Returns
the manifest contract: ``trends`` (array), ``patterns`` (list of str) and
``forecast`` (array).

Permissions
-----------
Declared: ``memory:read``. This skill touches no filesystem and no network.
All numbers are computed locally — no LLM provider is required (and none is
used), because every returned figure must be derived from the REAL input
data rather than invented.

Honesty note
------------
Every number in the result is computed in code from the real ``data``:
per-step deltas, mean, min/max, the OLS (least-squares) slope, total change
and linear trend segments in ``trends``, heuristic pattern strings that quote
real aggregates, and a ``forecast`` that is a plain linear projection of the
OLS fit extended ``forecast_periods`` steps beyond the last observation. No
value is fabricated and no provider reply is needed; the projection method is
documented here so callers know it is a simple extrapolation, not magic.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from skills._common import as_list, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]


def _parse_series(input_data: Dict[str, Any]) -> Tuple[List[str], List[float]]:
    """Extract ordered (timestamps, values) from the real input data."""
    raw = require(input_data, "data", list, "time series data")
    points = as_list(raw)
    if not points:
        raise SkillInputError("field 'data' must contain at least one point")
    timestamps: List[str] = []
    values: List[float] = []
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            raise SkillInputError(f"data[{i}] must be an object with timestamp/value")
        ts = point.get("timestamp")
        val = point.get("value")
        if not isinstance(ts, str) or isinstance(val, bool) or not isinstance(
            val, (int, float)
        ):
            raise SkillInputError(
                f"data[{i}] must have a string 'timestamp' and numeric 'value'"
            )
        timestamps.append(ts)
        values.append(float(val))
    return timestamps, values


def _linear_fit(values: List[float]) -> Tuple[float, float]:
    """Return (slope, intercept) of the ordinary least-squares fit over x=0..n-1."""
    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    denom = sum((x - x_mean) ** 2 for x in range(n))
    if denom == 0:  # single point -> flat fit through it
        return 0.0, values[0]
    slope = sum((x - x_mean) * (v - y_mean) for x, v in enumerate(values)) / denom
    return slope, y_mean - slope * x_mean


def _classify(slope: float, mean_abs: float) -> str:
    """Label a slope as rising/falling/stable relative to the data's scale."""
    threshold = 1e-6 * max(mean_abs, 1e-12)
    if slope > threshold:
        return "increasing"
    if slope < -threshold:
        return "decreasing"
    return "stable"


def _segment_trends(values: List[float]) -> List[Dict[str, Any]]:
    """
    Build honest trend segments: one entry per direction run in the real
    per-step deltas (a delta of exactly 0 continues the current segment).
    A single-point series yields one degenerate 'stable' segment.
    """
    eps = 1e-12
    segments: List[Dict[str, Any]] = []

    def _append(start: int, end: int) -> None:
        seg = values[start : end + 1]
        seg_slope, _ = _linear_fit(seg)
        segments.append(
            {
                "start_index": start,
                "end_index": end,
                "direction": _classify(seg_slope, abs(sum(seg) / len(seg))),
                "magnitude": round(seg[-1] - seg[0], 6),
                "slope": round(seg_slope, 6),
                "points": len(seg),
            }
        )

    if len(values) == 1:
        _append(0, 0)
        return segments

    start = 0
    direction = 0
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        step = 1 if delta > eps else (-1 if delta < -eps else 0)
        if step == 0:
            continue
        if direction == 0:
            direction = step
        elif step != direction:
            _append(start, i - 1)
            start = i - 1
            direction = step
    _append(start, len(values) - 1)
    return segments


def _patterns(values: List[float]) -> List[str]:
    """Textual patterns quoting only real aggregates of the data."""
    n = len(values)
    mean = sum(values) / n
    delta = values[-1] - values[0]
    lo, hi = min(values), max(values)
    slope, _ = _linear_fit(values)
    direction = _classify(slope, abs(mean))
    notes = [
        f"series of {n} observations over indices 0..{n - 1}",
        f"mean value {mean:.4g}; min {lo:.4g}; max {hi:.4g}",
        f"overall {direction} with a least-squares slope of {slope:.4g} per period",
    ]
    if n > 1:
        pct = (delta / values[0] * 100.0) if values[0] != 0 else 0.0
        if values[0] != 0:
            notes.append(f"total change {delta:.4g} ({pct:+.2f}%) from first to last")
        else:
            notes.append(f"total change {delta:.4g} from first to last")
        if (hi - lo) <= 1e-9 * max(abs(mean), 1.0):
            notes.append("values are nearly constant (no material volatility)")
    else:
        notes.append("single observation — no trend or volatility measurable")
    return notes


async def handle(input_data: dict, provider) -> dict:
    """
    Analyse the real time series and return ``trends``/``patterns``/``forecast``.

    ``provider`` is accepted for interface uniformity but intentionally unused:
    every number is computed from the input data in code.

    Raises:
        SkillInputError: Missing/malformed ``data`` or missing/bad ``metric``.
    """
    timestamps, values = _parse_series(input_data)
    metric = coerce_str(require(input_data, "metric", str, "metric name")).strip()
    if not metric:
        raise SkillInputError("field 'metric' must be a non-empty string")

    raw_periods = input_data.get("forecast_periods", 7)
    if isinstance(raw_periods, bool) or not isinstance(raw_periods, int):
        raise SkillInputError("field 'forecast_periods' must be an integer")
    forecast_periods = max(1, raw_periods)

    slope, intercept = _linear_fit(values)
    forecast = [
        round(slope * x + intercept, 6)
        for x in range(len(values), len(values) + forecast_periods)
    ]

    return {
        "metric": metric,
        "trends": _segment_trends(values),
        "patterns": _patterns(values),
        "mean": round(sum(values) / len(values), 6),
        "delta": round(values[-1] - values[0], 6),
        "slope": round(slope, 6),
        "forecast": forecast,
    }
