"""
Tests for the ``deep_research`` skill (web_research).

``ScriptedProvider`` is a deterministic stand-in for the LLM boundary only —
prompt construction, the best-effort network seam, input/output schema
validation, and the registry's executor all run for real. These tests are
OFFLINE: any URL handed to the handler is unroutable/unreachable (loopback
port 9), so the handler's honest "no search backend / fetch failed" path is
what actually executes. Live llama.cpp coverage lives behind the
``NEXA_E2E_LLAMACPP=1`` gate.

Note: pytest-asyncio is installed but ``asyncio_mode = "auto"`` is NOT set in
pyproject.toml, so every coroutine test is explicitly decorated with
``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.deep_research.handler import handle
from tests._skill_helpers import ScriptedProvider

OUTPUT_SCHEMA = skills.get_skill("deep_research").manifest.output_schema

# An unroutable/unreachable host so the best-effort fetch fails fast offline.
_UNREACHABLE_URL = "http://127.0.0.1:9/never-there"


def _valid_input() -> dict:
    return {
        "topic": "state of on-device small language models in 2026",
        "depth": "standard",
        "max_sources": 10,
    }


def _reply() -> str:
    return json.dumps(
        {
            "summary": "A synthesis of on-device SLMs in 2026.",
            "sources": [
                {
                    "url": "https://arxiv.org/abs/0000.0000",
                    "title": "Example paper",
                    "snippet": "On-device SLMs ...",
                    "credibility": "high",
                }
            ],
            "citations": ["[1] Example paper, arXiv."],
        }
    )


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rejects_missing_fields():
    with pytest.raises(SkillInputError):
        await handle({}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle({"topic": "x"}, ScriptedProvider())  # missing depth


@pytest.mark.asyncio
async def test_handle_rejects_wrong_types():
    with pytest.raises(SkillInputError):
        await handle(
            {"topic": "x", "depth": 5}, ScriptedProvider()
        )  # depth must be str


# ---------------------------------------------------------------------------
# 2. Happy path — model-provided summary + sources validate against manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid():
    provider = ScriptedProvider(reply=_reply())
    result = await handle(_valid_input(), provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert isinstance(result["summary"], str) and result["summary"]
    assert isinstance(result["sources"], list)
    assert isinstance(result["citations"], list)
    # Model-provided source passes through normalised.
    if result["sources"]:
        src = result["sources"][0]
        assert {"url", "title", "snippet", "credibility"} <= set(src)


# ---------------------------------------------------------------------------
# 3. Honest offline behaviour — unreachable URL, empty sources from model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offline_no_sources_is_schema_valid():
    # Model knows nothing / returns empty sources; handler must NOT invent URLs.
    provider = ScriptedProvider(
        reply=json.dumps({"summary": "Relying on internal knowledge.", "sources": [], "citations": []})
    )
    data = _valid_input()
    # Even when explicit URLs are supplied, they are unreachable here, so the
    # fetch degrades silently and the model is asked to synthesise offline.
    data_plus_unreachable = dict(data, urls=[_UNREACHABLE_URL])
    result = await handle(data_plus_unreachable, provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["sources"] == []
    assert result["summary"] == "Relying on internal knowledge."


# ---------------------------------------------------------------------------
# 4. Prompt fidelity — the real topic must reach the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_forwards_real_topic():
    provider = ScriptedProvider(reply=_reply())
    await handle(_valid_input(), provider)

    assert provider.calls, "provider never received a call"
    user_msg = provider.calls[0][-1]
    assert user_msg["role"] == "user"
    assert "on-device small language models" in user_msg["content"]
    assert "standard" in user_msg["content"]


# ---------------------------------------------------------------------------
# 5. Executor path — full registry round-trip validates output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    result = await skills.execute_skill(
        "deep_research", _valid_input(), ScriptedProvider(reply=_reply())
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert isinstance(result["summary"], str)
    assert isinstance(result["sources"], list)


# ---------------------------------------------------------------------------
# 6. LLM failure must surface, never be swallowed / fabricated over
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_surfaces_as_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_valid_input(), ScriptedProvider(fail=True))


# ---------------------------------------------------------------------------
# 7. Non-JSON model reply propagates (no silent fallback to fake content)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_json_reply_raises_value_error():
    with pytest.raises(ValueError):
        await handle(_valid_input(), ScriptedProvider(reply="no json here"))
