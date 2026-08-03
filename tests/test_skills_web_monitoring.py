"""
Tests for the ``web_monitoring`` skill (web_research).

``ScriptedProvider`` is accepted by the handler signature but intentionally
UNUSED by this skill — v0.1.0's web_monitoring does not call the LLM, it only
performs a single best-effort baseline fetch per URL. These tests are OFFLINE:
the URLs are unroutable/unreachable (loopback port 9), so every fetch fails
fast and the handler's honest degradation path executes: a baseline pass over
all URLs runs to completion, ``monitored`` is True, and ``changes_detected``
is the honest empty list (no prior snapshot, so no diff is ever fabricated).

Note: pytest-asyncio is installed but ``asyncio_mode = "auto"`` is NOT set in
pyproject.toml, so every coroutine test is explicitly decorated with
``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.web_monitoring.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("web_monitoring").manifest.output_schema

# Unroutable/unreachable hosts so each baseline fetch fails fast offline.
_UNREACHABLE_A = "http://127.0.0.1:9/pricing"
_UNREACHABLE_B = "http://127.0.0.1:9/status"


def _valid_input() -> dict:
    return {
        "urls": [_UNREACHABLE_A, _UNREACHABLE_B],
        "check_interval": 3600,
        "change_type": "price",
    }


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rejects_missing_fields():
    with pytest.raises(SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle(
            {"urls": [_UNREACHABLE_A], "check_interval": 60}, ScriptedProvider()
        )  # missing change_type


@pytest.mark.asyncio
async def test_handle_rejects_wrong_types():
    with pytest.raises(SkillInputError):
        await handle(
            {"urls": _UNREACHABLE_A, "check_interval": 60, "change_type": "any"},
            ScriptedProvider(),
        )  # urls must be a list
    with pytest.raises(SkillInputError):
        await handle(
            {"urls": [_UNREACHABLE_A], "check_interval": "60", "change_type": "any"},
            ScriptedProvider(),
        )  # check_interval must be an int


# ---------------------------------------------------------------------------
# 2. Honest offline/degraded path — schema-valid, monitored=True, no changes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offline_baseline_is_monitored_and_schema_valid():
    result = await handle(_valid_input(), ScriptedProvider())

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["monitored"] is True
    # First run: no prior snapshot -> an honest empty changes list, never a
    # fabricated diff even though every host is unreachable.
    assert result["changes_detected"] == []


@pytest.mark.asyncio
async def test_degraded_single_unreachable_url_still_monitored():
    # Even when the ONLY url cannot be fetched, the baseline pass completes.
    result = await handle(
        {"urls": [_UNREACHABLE_A], "check_interval": 1, "change_type": "any"},
        ScriptedProvider(),
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["monitored"] is True
    assert result["changes_detected"] == []


# ---------------------------------------------------------------------------
# 3. LLM failure — this skill does not use the provider, so fail=True must NOT
#    break it; the honest schema-valid result is still returned.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_does_not_break_monitoring():
    result = await handle(_valid_input(), ScriptedProvider(fail=True))
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["monitored"] is True
    assert result["changes_detected"] == []


# ---------------------------------------------------------------------------
# 4. Provider is never consulted — no LLM call is made by this skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_does_not_call_the_model():
    provider = ScriptedProvider(reply='{"irrelevant": true}')
    await handle(_valid_input(), provider)
    assert provider.calls == []


# ---------------------------------------------------------------------------
# 5. Executor path — full registry round-trip validates output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    result = await skills.execute_skill(
        "web_monitoring", _valid_input(), ScriptedProvider()
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["monitored"] is True
    assert result["changes_detected"] == []
