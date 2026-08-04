"""
Tests for the ``trend_analysis`` skill (web_research).

This handler computes every number in code from the REAL time series, so no
provider is required at all for the pure-math paths. Every async test is
explicitly marked — pyproject sets no ``asyncio_mode = "auto"``.
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.trend_analysis.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("trend_analysis").manifest.output_schema


def _series():
    return [
        {"timestamp": f"2026-07-{day:02d}", "value": float(value)}
        for day, value in [(1, 10), (2, 12), (3, 14), (4, 16), (5, 18)]
    ]


def _input(**overrides):
    payload = {"data": _series(), "metric": "weekly_active_users", "forecast_periods": 3}
    payload.update(overrides)
    return payload


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_data_or_metric_raise_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle({"metric": "users"}, None)
    with pytest.raises(SkillInputError):
        await handle({"data": _series()}, None)


@pytest.mark.asyncio
async def test_malformed_points_raise_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle(_input(data=[{"timestamp": "2026-07-01"}]), None)
    with pytest.raises(SkillInputError):
        await handle(_input(data=[{"timestamp": "2026-07-01", "value": "high"}]), None)


# 2. Happy path — schema-valid and every number is REAL -------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_and_math_is_real():
    result = await handle(_input(), None)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert set(result) >= {"trends", "patterns", "forecast"}
    assert isinstance(result["trends"], list)
    assert isinstance(result["patterns"], list)
    assert all(isinstance(p, str) for p in result["patterns"])

    # Real OLS fit over 10..18 step 2: slope == 2.0 exactly.
    assert result["forecast"] == pytest.approx([20.0, 22.0, 24.0])
    assert result["slope"] == pytest.approx(2.0)
    assert result["delta"] == pytest.approx(8.0)
    assert result["mean"] == pytest.approx(14.0)
    assert result["trends"][0]["direction"] == "increasing"

    # Quoted aggregates appear verbatim in the pattern strings.
    assert any("mean value 14" in p for p in result["patterns"])


# 3. Forecast honesty — length == forecast_periods, derived values ---------------


@pytest.mark.asyncio
async def test_forecast_length_matches_forecast_periods_and_is_derived():
    for periods in (1, 7):
        result = await handle(_input(forecast_periods=periods), None)
        assert validate_schema(OUTPUT_SCHEMA, result) == []
        assert len(result["forecast"]) == periods
        assert len(result["forecast"]) == result.get("forecast_periods", periods)
        # Values stay on the real line, not hallucinated.
        start, step = result["forecast"][0], result["forecast"][1] - result["forecast"][0] if periods > 1 else 2.0
        assert start == pytest.approx(20.0)
        assert step == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_default_forecast_periods_is_seven():
    result = await handle({"data": _series(), "metric": "users"}, None)
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert len(result["forecast"]) == 7


# 4. Direction honesty on a falling series ---------------------------------------


@pytest.mark.asyncio
async def test_decreasing_series_reports_falling_trend_and_negative_forecast():
    result = await handle(
        {"data": [{"timestamp": "t0", "value": 10.0}, {"timestamp": "t1", "value": 4.0}],
         "metric": "latency", "forecast_periods": 1},
        None,
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["trends"][0]["direction"] == "decreasing"
    assert result["forecast"][0] == pytest.approx(-2.0)


# 5. Executor path — full registry round-trip -------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    result = await skills.execute_skill("trend_analysis", _input(), None)
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert len(result["forecast"]) == 3


# 6. Provider is accepted but never needed — failure-provider still works ---------


@pytest.mark.asyncio
async def test_provider_is_not_required_for_pure_math():
    result = await handle(_input(), ScriptedProvider(fail=True))
    assert validate_schema(OUTPUT_SCHEMA, result) == []
