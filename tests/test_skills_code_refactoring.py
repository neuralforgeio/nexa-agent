"""
Tests for the ``code_refactoring`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads, prompt construction, schema
validation, and the registry executor all run for real against a temporary
workspace (``FORGE_WORKSPACE`` pointed at ``tmp_path``).

Honesty invariant under test: the executor path must leave the workspace
file byte-for-byte unchanged and report ``applied is False`` — auto-apply is
intentionally opt-in/disabled in this handler.
"""

from __future__ import annotations

import json

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.code_refactoring.handler import handle
from tests._skill_helpers import ScriptedProvider

APP_SRC = """\
def total(items):
    t = 0
    for it in items:
        t = t + it
    return t


x = total([1, 2, 3])
print(x)
"""

GOOD_REPLY = json.dumps(
    {
        "refactors": [
            {
                "type": "simplify",
                "description": "Replace the manual accumulation loop with sum().",
                "before": "    t = 0\n    for it in items:\n        t = t + it\n    return t",
                "after": "    return sum(items)",
                "line": 2,
            },
            {
                "type": "rename",
                "description": "Rename 'it' to the clearer 'amount'.",
                "before": "    for it in items:",
                "after": "    for amount in items:",
                "line": 3,
            },
        ],
        "applied": True,  # model may claim applied; handler must NOT honour it
    }
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(APP_SRC, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # openforge.config.FORGE_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_skills_code_*).
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("code_refactoring").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_input_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Missing file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"file_path": "nope_missing.py", "refactor_type": "all"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 3. Happy path: normalised output validates against the manifest schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_two_refactors_schema_valid(ws):
    out = await handle(
        {"file_path": "app.py", "refactor_type": "all"},
        ScriptedProvider(reply=GOOD_REPLY),
    )

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert len(out["refactors"]) == 2
    for ref in out["refactors"]:
        assert set(ref.keys()) == {"type", "description", "before", "after", "line"}
        assert isinstance(ref["line"], int)
    assert out["refactors"][0]["type"] == "simplify"
    assert out["refactors"][1]["type"] == "rename"
    # Even when the model claims applied=True, the handler reports it
    # honestly: nothing was written.
    assert out["applied"] is False


# ---------------------------------------------------------------------------
# 4. Prompt fidelity: the real file text reaches the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_file_content(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle({"file_path": "app.py", "refactor_type": "simplify"}, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "def total(items):" in user_prompt
    assert "t = t + it" in user_prompt
    assert "x = total([1, 2, 3])" in user_prompt
    assert "simplify" in user_prompt  # requested refactor_type is passed along
    # The system turn pins the single-JSON-object output contract.
    assert messages[0]["role"] == "system"
    assert "refactors" in messages[0]["content"]
    assert "applied" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 5. Full executor path: validated AND the file is never mutated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_validates_and_does_not_mutate_file(ws):
    before = (ws / "app.py").read_text(encoding="utf-8")
    out = await skills.execute_skill(
        "code_refactoring",
        {"file_path": "app.py", "refactor_type": "all"},
        ScriptedProvider(reply=GOOD_REPLY),
    )

    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["applied"] is False
    # Honest default: suggestions only — the workspace file is untouched.
    assert (ws / "app.py").read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# 6. LLM failure propagates (never swallowed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await handle(
            {"file_path": "app.py", "refactor_type": "rename"},
            ScriptedProvider(fail=True),
        )
