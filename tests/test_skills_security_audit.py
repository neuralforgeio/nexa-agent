"""
Tests for the ``security_audit`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads (single-file AND directory
scanning), prompt construction, schema validation, and the registry executor
all run for real against a temporary workspace (``FORGE_WORKSPACE`` pointed at
``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.security_audit.handler import handle
from tests._skill_helpers import ScriptedProvider

VULN_APP_PY = (
    "import sqlite3\n"
    "\n"
    "def get_user(username):\n"
    "    conn = sqlite3.connect('app.db')\n"
    '    cur = conn.cursor()\n'
    "    cur.execute(\"SELECT * FROM users WHERE name = '%s'\" % username)\n"
    "    return cur.fetchone()\n"
)

UTILS_PY = (
    "import hashlib\n"
    "\n"
    "def weak_hash(password):\n"
    "    # Fast + unsalted: convenient for tests, terrible for passwords.\n"
    "    return hashlib.md5(password.encode()).hexdigest()\n"
)

GOOD_REPLY = (
    '{"vulnerabilities": [{'
    '"cwe_id": "CWE-89", '
    '"severity": "critical", '
    '"location": "app.py:6", '
    '"description": "SQL injection: user-controlled username is interpolated '
    'directly into the SELECT via % formatting.", '
    '"remediation": "Use a parameterised query: '
    "cur.execute('SELECT * FROM users WHERE name = ?', (username,)).\""
    "}]}"
)

DIR_REPLY = (
    '{"vulnerabilities": [{'
    '"cwe_id": "CWE-327", '
    '"severity": "high", '
    '"location": "utils.py:5", '
    '"description": "MD5 is cryptographically broken and unsuitable for '
    'password hashing.", '
    '"remediation": "Use bcrypt, scrypt, or argon2 with a per-user salt."'
    "}]}"
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(VULN_APP_PY, encoding="utf-8")
    (tmp_path / "utils.py").write_text(UTILS_PY, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # tools._paths captured FORGE_WORKSPACE at import time — repoint it.
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("security_audit").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_input_raises_input_error(ws):
    # Neither file_path nor directory_path, and no scan_depth at all.
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Missing file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"file_path": "nope_missing.py", "scan_depth": "quick"},
            ScriptedProvider(reply=GOOD_REPLY),
        )


# ---------------------------------------------------------------------------
# 3. Happy path (file) + schema conformance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_file_schema_and_keys(ws):
    out = await handle(
        {"file_path": "app.py", "scan_depth": "deep"},
        ScriptedProvider(reply=GOOD_REPLY),
    )

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    assert len(out["vulnerabilities"]) == 1
    v = out["vulnerabilities"][0]
    assert set(v.keys()) == {
        "cwe_id",
        "severity",
        "location",
        "description",
        "remediation",
    }
    assert all(isinstance(v[k], str) for k in v)
    assert v["cwe_id"] == "CWE-89"
    assert v["severity"] == "critical"
    assert "SQL injection" in v["description"]


# ---------------------------------------------------------------------------
# 4. Prompt fidelity — the REAL file content reached the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_file_content(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle({"file_path": "app.py", "scan_depth": "quick"}, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    # The real file bytes read from the workspace are inside the prompt.
    assert "cur.execute(" in user_prompt
    assert "username" in user_prompt
    assert "app.py" in user_prompt
    assert "quick" in user_prompt
    # The system turn pins the JSON output contract.
    assert messages[0]["role"] == "system"
    assert "vulnerabilities" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 5. Directory scan — real files under directory_path, 1 finding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_directory_scan_happy_path(ws):
    provider = ScriptedProvider(reply=DIR_REPLY)
    out = await handle(
        {"directory_path": ".", "scan_depth": "deep"}, provider
    )

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert len(out["vulnerabilities"]) == 1
    v = out["vulnerabilities"][0]
    assert set(v.keys()) == {
        "cwe_id",
        "severity",
        "location",
        "description",
        "remediation",
    }
    assert v["cwe_id"] == "CWE-327"

    # Prompt fidelity for the directory scan: BOTH real files' bytes are in
    # the user prompt — the directory listing was read for real.
    user_prompt = provider.last_user_message(provider.calls[0])
    assert "SELECT * FROM users" in user_prompt        # app.py
    assert "hashlib.md5" in user_prompt                # utils.py


# ---------------------------------------------------------------------------
# 6. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "security_audit",
        {"file_path": "app.py", "scan_depth": "deep"},
        ScriptedProvider(reply=GOOD_REPLY),
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["vulnerabilities"][0]["cwe_id"] == "CWE-89"


# ---------------------------------------------------------------------------
# 7. LLM failure propagates as RuntimeError (no fabrication)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await skills.execute_skill(
            "security_audit",
            {"file_path": "app.py", "scan_depth": "quick"},
            ScriptedProvider(fail=True),
        )
