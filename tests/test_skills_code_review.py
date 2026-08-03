"""
Tests for the ``code_review`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads, prompt construction, schema
validation, and the registry executor all run for real against a temporary
workspace (``NEXA_WORKSPACE`` pointed at ``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.code_review.handler import handle
from tests._skill_helpers import ScriptedProvider

APP_PY = "def f(x):\n    return 1/0\n"

GOOD_REPLY = (
    "```json\n"
    '{"issues": [{"severity": "high", "line": 2, '
    '"message": "Division by zero: 1/0 always raises ZeroDivisionError.", '
    '"suggestion": "Guard the divisor or return a defined fallback before dividing."}], '
    '"summary": "Found 1 definite bug: division by zero in f()."}\n'
    "```"
)


class ReplyProvider(ScriptedProvider):
    """ScriptedProvider streaming a fixed reply string token-by-token."""

    def __init__(self, reply: str) -> None:
        super().__init__(events=[("token", reply), ("done", None)])


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(APP_PY, encoding="utf-8")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # nexa.config.NEXA_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_file_tools_*).
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("code_review").manifest


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
            {"file_path": "nope_missing.py", "focus": "bugs"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 3. Happy path + schema conformance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_and_issue_keys(ws):
    out = await handle(
        {"file_path": "app.py", "focus": "bugs"}, ReplyProvider(GOOD_REPLY)
    )

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    # The scripted model finding is what comes back, normalised.
    assert len(out["issues"]) == 1
    issue = out["issues"][0]
    assert set(issue.keys()) == {"severity", "line", "message", "suggestion"}
    assert isinstance(issue["severity"], str)
    assert isinstance(issue["line"], int)
    assert isinstance(issue["message"], str)
    assert isinstance(issue["suggestion"], str)
    assert issue["line"] == 2
    assert "1/0" in issue["message"]
    assert isinstance(out["summary"], str) and out["summary"]


# ---------------------------------------------------------------------------
# 4. Prompt fidelity — the REAL file content reached the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_file_content(ws):
    provider = ReplyProvider(GOOD_REPLY)
    await handle({"file_path": "app.py", "focus": "all"}, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    # The exact bytes read from the workspace file are inside the prompt.
    assert "return 1/0" in user_prompt
    assert "def f(x):" in user_prompt
    # Focus also reached the prompt.
    assert "all" in user_prompt
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "issues" in messages[0]["content"]
    assert "summary" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 5. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "code_review",
        {"file_path": "app.py", "focus": "bugs"},
        ReplyProvider(GOOD_REPLY),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["issues"][0]["line"] == 2
    assert "1/0" in out["issues"][0]["message"]


# ---------------------------------------------------------------------------
# 6. Junk model output — handler refuses to fabricate findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_junk_model_output_raises_value_error(ws):
    # Unparseable reply: ask_llm_json (no fallback) raises ValueError rather
    # than emitting made-up review findings.
    provider = ReplyProvider("I cannot review that. <no JSON at all>")
    with pytest.raises(ValueError):
        await skills.execute_skill(
            "code_review",
            {"file_path": "app.py", "focus": "bugs"},
            provider,
        )
