"""
Tests for the ``content_extraction`` skill (web_research).

``ScriptedProvider`` is a deterministic stand-in for the LLM boundary only.
These tests are OFFLINE and never touch the real network:

  * The degradation tests point at unroutable/unreachable hosts (loopback
    port 9) so the fetch fails fast and the handler's honest
    ``{"extracted_data": {}, "confidence": 0.0}`` path runs without calling
    the model on empty content.
  * The one "successful fetch" test monkeypatches ``tool_api.http_client`` to
    return a stub client yielding canned page text — exercising the real
    extraction path deterministically, with no network.

Note: pytest-asyncio is installed but ``asyncio_mode = "auto"`` is NOT set in
pyproject.toml, so every coroutine test is explicitly decorated with
``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.content_extraction import handler as ce_handler
from skills.web_research.content_extraction.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("content_extraction").manifest.output_schema

# Unroutable/unreachable host so the fetch fails fast offline.
_UNREACHABLE_URL = "http://127.0.0.1:9/product/42"


def _valid_input() -> dict:
    return {
        "url": _UNREACHABLE_URL,
        "extraction_schema": {"title": "string", "price": "number", "in_stock": "boolean"},
    }


# A tiny stub for the "successful fetch" test — returns a canned page body.
class _StubResponse:
    status_code = 200
    text = "<html><title>Widget</title>Price: 19.99 USD. In stock.</html>"


class _StubClient:
    async def get(self, url):
        return _StubResponse()

    async def aclose(self):
        return None


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rejects_missing_fields():
    with pytest.raises(SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle({"url": _UNREACHABLE_URL}, ScriptedProvider())  # no extraction_schema


@pytest.mark.asyncio
async def test_handle_rejects_wrong_types():
    with pytest.raises(SkillInputError):
        await handle(
            {"url": 42, "extraction_schema": {}}, ScriptedProvider()
        )  # url must be str
    with pytest.raises(SkillInputError):
        await handle(
            {"url": _UNREACHABLE_URL, "extraction_schema": "title"}, ScriptedProvider()
        )  # extraction_schema must be object


# ---------------------------------------------------------------------------
# 2. Honest OFFLINE/degraded path — fetch fails, model is NOT consulted, and
#    the honest empty result validates against the manifest. No raise.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offline_fetch_failure_degrades_honestly():
    provider = ScriptedProvider(
        reply='{"extracted_data": {"title": "SHOULD NOT BE USED"}, "confidence": 0.9}'
    )
    result = await handle(_valid_input(), provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    # Honest degradation: nothing fetched -> nothing extracted, confidence 0.
    assert result["extracted_data"] == {}
    assert result["confidence"] == 0.0
    # The model must NOT be asked to hallucinate from empty content.
    assert provider.calls == []


@pytest.mark.asyncio
async def test_llm_failure_offline_still_degrades_honestly_no_raise():
    # fail=True makes the provider raise IF consulted; offline the fetch fails
    # first, so the honest degraded result is returned and nothing raises.
    result = await handle(_valid_input(), ScriptedProvider(fail=True))
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["extracted_data"] == {}
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# 3. Successful-fetch path (stubbed client) — real extraction via the model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_fetch_extracts_via_model(monkeypatch):
    monkeypatch.setattr(ce_handler.tool_api, "http_client", lambda **kw: _StubClient())
    provider = ScriptedProvider(
        reply=json.dumps(
            {
                "extracted_data": {"title": "Widget", "price": 19.99, "in_stock": True},
                "confidence": 0.95,
            }
        )
    )
    result = await handle(_valid_input(), provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["extracted_data"]["title"] == "Widget"
    assert result["extracted_data"]["price"] == 19.99
    assert result["extracted_data"]["in_stock"] is True
    assert 0.0 <= result["confidence"] <= 1.0
    # Real page content reached the model (prompt fidelity).
    assert provider.calls, "model was never consulted after a successful fetch"
    user_msg = provider.calls[0][-1]["content"]
    assert "Widget" in user_msg and "19.99" in user_msg


# ---------------------------------------------------------------------------
# 4. Executor path — full registry round-trip validates output (offline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip_offline():
    result = await skills.execute_skill(
        "content_extraction", _valid_input(), ScriptedProvider()
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["extracted_data"] == {}
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# 5. Confidence is always clamped/normalised into [0, 1] on the success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_clamped(monkeypatch):
    monkeypatch.setattr(ce_handler.tool_api, "http_client", lambda **kw: _StubClient())
    provider = ScriptedProvider(
        reply=json.dumps({"extracted_data": {"title": "Widget"}, "confidence": 3.7})
    )
    result = await handle(_valid_input(), provider)
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert 0.0 <= result["confidence"] <= 1.0
