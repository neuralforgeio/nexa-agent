"""
Tests for the ``translation`` skill (web_research).

``ScriptedProvider`` is a deterministic stand-in for the LLM boundary only —
prompt construction, input/output schema validation, and the registry's
executor all run for real. Live llama.cpp coverage lives behind the
``NEXA_E2E_LLAMACPP=1`` gate.

Note: pytest-asyncio is installed but ``asyncio_mode = "auto"`` is NOT set in
pyproject.toml, so every coroutine test is explicitly decorated with
``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.translation.handler import handle
from tests._skill_helpers import ScriptedProvider

# NOTE: tests._skill_helpers.ScriptedProvider was repaired at the source (the
# unconditional bare ``return`` that streamed zero tokens was removed), so the
# stock stand-in is used as-is here — no module-level monkeypatch is needed.

OUTPUT_SCHEMA = skills.get_skill("translation").manifest.output_schema


def _valid_input() -> dict:
    return {"text": "Hello world", "from": "en", "to": "fr"}


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rejects_missing_fields():
    with pytest.raises(SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_handle_rejects_wrong_type():
    with pytest.raises(SkillInputError):
        await handle({"text": 1, "from": "en", "to": "fr"}, ScriptedProvider())
    with pytest.raises(SkillInputError):
        await handle({"text": "hi", "from": "en"}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path — output validates against the manifest schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid():
    reply = (
        '{"translated_text": "Bonjour le monde",'
        ' "detected_language": "en",'
        ' "confidence": 0.98}'
    )
    provider = ScriptedProvider(reply=reply)
    result = await handle(_valid_input(), provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["translated_text"] == "Bonjour le monde"
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["detected_language"] == "en"


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real text/languages must reach the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_forwards_real_text_and_target_language():
    provider = ScriptedProvider(reply='{"translated_text": "x", "confidence": 0.9}')
    await handle(_valid_input(), provider)

    assert provider.calls, "provider never received a call"
    user_msg = provider.calls[0][-1]
    assert user_msg["role"] == "user"
    assert "Hello world" in user_msg["content"]
    assert "fr" in user_msg["content"]
    assert "en" in user_msg["content"]


# ---------------------------------------------------------------------------
# 4. Executor path — full registry round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    reply = '{"translated_text": "Bonjour le monde", "confidence": 0.97}'
    result = await skills.execute_skill(
        "translation", _valid_input(), ScriptedProvider(reply=reply)
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["translated_text"] == "Bonjour le monde"


# ---------------------------------------------------------------------------
# 5. LLM failure must surface, never be swallowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_surfaces_as_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_valid_input(), ScriptedProvider(fail=True))


# ---------------------------------------------------------------------------
# 6. Non-JSON model reply — this handler raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_json_reply_raises_value_error():
    with pytest.raises(ValueError):
        await handle(_valid_input(), ScriptedProvider(reply="not json"))
