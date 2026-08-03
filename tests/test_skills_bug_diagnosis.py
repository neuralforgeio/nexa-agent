"""
Tests for the ``bug_diagnosis`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Context-file reads, prompt construction,
schema validation, and the registry executor all run for real against a
temporary workspace (``NEXA_WORKSPACE`` pointed at ``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.bug_diagnosis.handler import handle
from tests._skill_helpers import ScriptedProvider

STACK_TRACE = (
    "Traceback (most recent call last):\n"
    '  File "mod.py", line 6, in boom\n'
    "    return 1 / x\n"
    "ZeroDivisionError: division by zero"
)

CONTEXT_SNIPPET = "def boom(x):\n    return 1 / x\n"

GOOD_REPLY = (
    '```json\n'
    '{"root_cause": "boom() divides by x without guarding against zero", '
    '"affected_files": ["mod.py"], '
    '"fix_suggestion": "check x != 0 before dividing or catch '
    'ZeroDivisionError", '
    '"confidence": 0.9}\n'
    "```"
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text(CONTEXT_SNIPPET, encoding="utf-8")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # NEXA_WORKSPACE is captured at import time by tools._paths, so the env
    # var alone is not enough — repoint the already-imported reference.
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("bug_diagnosis").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_stack_trace_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_context_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {
                "stack_trace": STACK_TRACE,
                "context_files": ["nope_missing.py"],
            },
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Happy path + schema (stack trace only — primary input, no file needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await handle({"stack_trace": STACK_TRACE}, provider)

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    assert out["root_cause"].startswith("boom()")
    assert out["affected_files"] == ["mod.py"]
    assert all(isinstance(f, str) for f in out["affected_files"])
    assert "x != 0" in out["fix_suggestion"]
    assert isinstance(out["confidence"], float)
    assert 0.0 <= out["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real stack trace AND context file reached the
#    provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_trace_and_context(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(
        {"stack_trace": STACK_TRACE, "context_files": ["mod.py"]},
        provider,
    )

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    # The verbatim stack trace is embedded.
    assert "ZeroDivisionError: division by zero" in user_prompt
    assert 'File "mod.py", line 6' in user_prompt
    # The verbatim context file read from disk is embedded.
    assert "def boom(x):" in user_prompt
    assert "return 1 / x" in user_prompt
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "root_cause" in messages[0]["content"]
    assert "confidence" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await skills.execute_skill(
        "bug_diagnosis",
        {"stack_trace": STACK_TRACE, "context_files": ["mod.py"]},
        provider,
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["affected_files"] == ["mod.py"]
    assert 0.0 <= out["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# 5. LLM failure and junk propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates(ws):
    with pytest.raises(RuntimeError):
        await handle({"stack_trace": STACK_TRACE}, ScriptedProvider(fail=True))
