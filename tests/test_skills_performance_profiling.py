"""
Tests for the ``performance_profiling`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. File reads, prompt construction, schema
validation, and the registry executor all run for real against a temporary
workspace (``FORGE_WORKSPACE`` pointed at ``tmp_path``).
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.code_intelligence.performance_profiling.handler import handle
from tests._skill_helpers import ScriptedProvider

SNIPPET = (
    "def process(items):\n"
    "    result = []\n"
    "    for item in items:\n"
    "        for other in items:\n"
    "            if item == other:\n"
    "                result.append(item)\n"
    "    return result\n"
)

GOOD_REPLY = (
    '```json\n'
    '{"bottlenecks": ['
    '{"type": "algorithmic", '
    '"location": "process() nested loops", '
    '"impact": "O(n^2) comparisons dominate as the item list grows", '
    '"suggestion": "use a dict/set for membership tests instead of an inner '
    'loop"}], '
    '"profile_summary": "Static analysis only; the nested-loop membership '
    'check is the main hotspot under repeated batches."}\n'
    "```"
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "calc.py").write_text(SNIPPET, encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # FORGE_WORKSPACE is captured at import time by tools._paths, so the env
    # var alone is not enough — repoint the already-imported reference.
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("performance_profiling").manifest


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
            {"file_path": "nope_missing.py", "scenario": "10k items batch"},
            ScriptedProvider(),
        )


# ---------------------------------------------------------------------------
# 2. Happy path + schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await handle(
        {"file_path": "calc.py", "scenario": "process 10000 items per batch"},
        provider,
    )

    # Output conforms to the manifest's output_schema.
    assert R.validate_schema(_manifest().output_schema, out) == []

    assert isinstance(out["bottlenecks"], list) and len(out["bottlenecks"]) == 1
    b = out["bottlenecks"][0]
    assert set(b.keys()) == {"type", "location", "impact", "suggestion"}
    assert all(isinstance(v, str) for v in b.values())
    assert b["type"] == "algorithmic"
    assert isinstance(out["profile_summary"], str) and out["profile_summary"]


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real file content and scenario reached the
#    provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_file_and_scenario(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(
        {"file_path": "calc.py", "scenario": "process 10000 items per batch"},
        provider,
    )

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    # The verbatim source read from disk is embedded in the user turn.
    assert "def process(items):" in user_prompt
    assert "for other in items:" in user_prompt
    assert "result.append(item)" in user_prompt
    # The scenario text is embedded too.
    assert "process 10000 items per batch" in user_prompt
    # The system turn pins the JSON output contract and honest static mode.
    assert messages[0]["role"] == "system"
    assert "bottlenecks" in messages[0]["content"]
    assert "profile_summary" in messages[0]["content"]
    assert "STATIC" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    provider = ScriptedProvider(reply=GOOD_REPLY)
    out = await skills.execute_skill(
        "performance_profiling",
        {"file_path": "calc.py", "scenario": "plan 50 steps on a 4k budget"},
        provider,
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["bottlenecks"][0]["type"] == "algorithmic"
    assert "Static analysis" in out["profile_summary"]


# ---------------------------------------------------------------------------
# 5. LLM failure and junk propagate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates(ws):
    with pytest.raises(RuntimeError):
        await handle(
            {"file_path": "calc.py", "scenario": "batch load"},
            ScriptedProvider(fail=True),
        )
