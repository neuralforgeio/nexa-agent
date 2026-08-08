"""
Tests for the ``code_explanation`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads, prompt construction, schema
validation, and the registry executor all run for real against a temporary
workspace (``FORGE_WORKSPACE`` pointed at ``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.code_explanation.handler import handle
from tests._skill_helpers import ScriptedProvider

SNIPPET = "def add(a, b):\n    return a + b\n"

GOOD_REPLY = (
    '```json\n{"explanation": "Adds two numbers.", '
    '"flow_steps": ["take a and b", "return a+b"], '
    '"dependencies": []}\n```'
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "snippet.py").write_text(SNIPPET, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # openforge.config.FORGE_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_file_tools_*).
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("code_explanation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_fields_raise_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_bad_detail_level_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle(
            {"file_path": "snippet.py", "detail_level": "verbose"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Missing file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"file_path": "nope_missing.py", "detail_level": "brief"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 3. Happy path + 4. prompt fidelity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_flow_and_schema(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await handle(
        {"file_path": "snippet.py", "detail_level": "brief"}, provider
    )

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    # The scripted model reply is what comes back, normalised.
    assert out["explanation"] == "Adds two numbers."
    assert out["flow_steps"] == ["take a and b", "return a+b"]
    assert out["dependencies"] == []
    assert all(isinstance(s, str) for s in out["flow_steps"])
    assert all(isinstance(d, str) for d in out["dependencies"])

    # Prompt fidelity: the provider received the REAL file contents.
    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "def add" in user_prompt
    assert "return a + b" in user_prompt
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "explanation" in messages[0]["content"]
    assert "flow_steps" in messages[0]["content"]
    assert "dependencies" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 5. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await skills.execute_skill(
        "code_explanation",
        {"file_path": "snippet.py", "detail_level": "brief"},
        provider,
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["explanation"] == "Adds two numbers."


# ---------------------------------------------------------------------------
# 6. Invalid model output surfaces through the executor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_junk_model_output_raises_output_error(ws):
    # An empty JSON object parses fine but lacks the required "explanation"
    # key, so the executor's output_schema validation must reject it.
    provider = ScriptedProvider(reply="{}")
    with pytest.raises(R.SkillOutputError):
        await skills.execute_skill(
            "code_explanation",
            {"file_path": "snippet.py", "detail_level": "brief"},
            provider,
        )
