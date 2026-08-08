"""
Tests for the ``summarization`` skill (web_research).

``ScriptedProvider`` is a deterministic stand-in *only* for the LLM boundary —
prompt construction, real workspace file reads, schema validation, and the
registry executor all run for real. Every async test is decorated with
``@pytest.mark.asyncio`` (the pyproject has no ``asyncio_mode = "auto"``).
"""

from __future__ import annotations

import pytest

import skills
from skills.registry import SkillInputError, validate_schema
from skills.web_research.summarization.handler import handle
from tests._skill_helpers import ScriptedProvider

MANIFEST = skills.get_skill("summarization").manifest
OUTPUT_SCHEMA = MANIFEST.output_schema

REPLY = (
    '{"summary": "Hiring is paused and infrastructure spend was cut 20%.",'
    ' "key_points": ["hiring paused", "infra spend cut 20%"]}'
)


def _input() -> dict:
    return {
        "content": "Quarterly planning notes: hiring paused, infra spend cut "
        "20%, focus shifts to retention.",
        "length": "brief",
        "style": "bullet",
    }


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    """Sandbox the Nexa workspace at a temp dir (env var + chdir + cached const)."""
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


# 1. Input validation ---------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_source_raises_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle({"length": "brief", "style": "bullet"}, ScriptedProvider())


@pytest.mark.asyncio
async def test_wrong_type_content_raises_skill_input_error():
    with pytest.raises(SkillInputError):
        await handle(
            {"content": 123, "length": "brief", "style": "bullet"}, ScriptedProvider()
        )


# 2. Happy path — schema-valid, word_count is honest --------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_and_honest_word_count():
    provider = ScriptedProvider(reply=REPLY)
    result = await handle(_input(), provider)

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert isinstance(result["summary"], str)
    assert isinstance(result["key_points"], list)
    assert all(isinstance(p, str) for p in result["key_points"])
    assert isinstance(result["word_count"], int)
    # word_count must be the REAL word count of the produced summary.
    assert result["word_count"] == len(result["summary"].split())
    assert result["word_count"] > 0


# 3. Prompt fidelity — the real content reaches the provider -------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_content_and_options():
    provider = ScriptedProvider(reply=REPLY)
    await handle(_input(), provider)

    assert provider.calls, "provider never received a call"
    user_msgs = [m for m in provider.calls[0] if m.get("role") == "user"]
    assert user_msgs
    payload = user_msgs[-1]["content"]
    assert "hiring paused" in payload
    assert "brief" in payload
    assert "bullet" in payload


# 4. Real workspace file input via file_path ------------------------------------


@pytest.mark.asyncio
async def test_file_path_reads_real_workspace_file(ws):
    (ws / "notes.txt").write_text("Real file body: deploys moved to Fridays.", "utf-8")
    provider = ScriptedProvider(reply=REPLY)
    result = await handle(
        {"file_path": "notes.txt", "length": "standard", "style": "paragraph"},
        provider,
    )

    assert validate_schema(OUTPUT_SCHEMA, result) == []
    payload = provider.calls[0][-1]["content"]
    assert "Real file body" in payload  # the genuine file contents were read

    with pytest.raises(SkillInputError):
        await handle(
            {"file_path": "missing.txt", "length": "brief", "style": "brief"},
            ScriptedProvider(),
        )
    with pytest.raises(SkillInputError):
        await handle(
            {"file_path": "../escape.txt", "length": "brief", "style": "bullet"},
            ScriptedProvider(),
        )


# 5. Executor path — full registry round-trip -----------------------------------


@pytest.mark.asyncio
async def test_execute_skill_roundtrip():
    result = await skills.execute_skill(
        "summarization", _input(), ScriptedProvider(reply=REPLY)
    )
    assert validate_schema(OUTPUT_SCHEMA, result) == []
    assert result["word_count"] == len(result["summary"].split())


# 6. LLM failure surfaces, never swallowed --------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(_input(), ScriptedProvider(fail=True))
