"""
Tests for the ``test_generation`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads, prompt construction, schema
validation, and the registry executor all run for real against a temporary
workspace (``NEXA_WORKSPACE`` pointed at ``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.test_generation.handler import handle
from tests._skill_helpers import ScriptedProvider

SNIPPET = (
    "def add(a, b):\n"
    "    return a + b\n"
    "\n"
    "def div(a, b):\n"
    "    if b == 0:\n"
    "        raise ValueError('division by zero')\n"
    "    return a / b\n"
)

GOOD_REPLY = (
    '```json\n'
    '{"test_code": "import pytest\\nfrom snippet import add, div\\n\\n'
    'def test_add():\\n    assert add(1, 2) == 3\\n", '
    '"test_file_path": "tests/test_snippet.py", '
    '"coverage_estimate": 85}\n'
    "```"
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "snippet.py").write_text(SNIPPET, encoding="utf-8")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # NEXA_WORKSPACE is captured at import time by tools._paths, so the env
    # var alone is not enough — repoint the already-imported reference.
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("test_generation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_fields_raise_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"file_path": "nope_missing.py", "framework": "pytest"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Happy path + schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await handle(
        {"file_path": "snippet.py", "framework": "pytest"}, provider
    )

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    assert isinstance(out["test_code"], str) and "def test_add" in out["test_code"]
    assert out["test_file_path"] == "tests/test_snippet.py"
    assert isinstance(out["coverage_estimate"], int)
    assert out["coverage_estimate"] == 85
    assert 0 <= out["coverage_estimate"] <= 100


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real file content reached the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_file_content(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(
        {
            "file_path": "snippet.py",
            "framework": "pytest",
            "function_name": "div",
        },
        provider,
    )

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    # The verbatim source read from disk is embedded in the user turn.
    assert "def add(a, b):" in user_prompt
    assert "return a / b" in user_prompt
    assert "raise ValueError('division by zero')" in user_prompt
    assert "div" in user_prompt  # requested focus function
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "test_code" in messages[0]["content"]
    assert "coverage_estimate" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await skills.execute_skill(
        "test_generation",
        {"file_path": "snippet.py", "framework": "unittest"},
        provider,
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["test_file_path"] == "tests/test_snippet.py"
    assert isinstance(out["coverage_estimate"], int)


# ---------------------------------------------------------------------------
# 5. LLM failure and junk propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates(ws):
    with pytest.raises(RuntimeError):
        await handle(
            {"file_path": "snippet.py", "framework": "pytest"},
            ScriptedProvider(fail=True),
        )
