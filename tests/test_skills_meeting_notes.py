"""
Tests for the ``meeting_notes`` skill (communication).

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. The workspace file check, prompt
construction, schema validation, and the registry executor all run for real
against a temporary workspace (``FORGE_WORKSPACE`` pointed at ``tmp_path``).

For prompt-fidelity these tests use the ``events=[("token", reply),
("done", None)]`` form of the (chunk-agnostic) stock provider so the whole
scripted reply is streamed verbatim — no substring truncation across chunks.

Note: pytest-asyncio runs in STRICT mode in this repo, so every coroutine
test is explicitly decorated with ``@pytest.mark.asyncio``.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.communication.meeting_notes.handler import handle
from tests._skill_helpers import ScriptedProvider

DUMMY_AUDIO = b"\x00" * 32  # opaque placeholder bytes — NOT real audio

GOOD_REPLY = (
    '{"transcript": "",'
    ' "action_items": ['
    '   {"task": "Circulate Q3 budget draft", "assignee": "Ari", "due_date": "2026-08-07"},'
    '   {"task": "Book sprint 43 planning"},'
    '   "send the minutes to the team"'
    " ],"
    ' "decisions": ["Ship v4.4 next week"],'
    ' "summary": "Context-derived skeleton notes for the sprint review."}'
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "meeting.mp3").write_bytes(DUMMY_AUDIO)
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # openforge.config.FORGE_WORKSPACE is captured at import time, so the env var
    # alone is not enough — repoint the already-imported reference used by
    # tools._paths.resolve_in_workspace (same pattern as test_file_tools_*).
    monkeypatch.setattr("tools._paths.FORGE_WORKSPACE", tmp_path)
    return tmp_path


def _manifest():
    return skills.get_skill("meeting_notes").manifest


def _valid_input() -> dict:
    return {
        "audio_path": "meeting.mp3",
        "meeting_context": "Sprint 42 review: shipping v4.4, Q3 budget draft assigned to Ari.",
        "attendees": ["Dearly", "Ari", "Maya"],
    }


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_audio_path_raises_input_error(ws):
    with pytest.raises(R.SkillInputError):
        await handle({}, ScriptedProvider())


@pytest.mark.asyncio
async def test_missing_file_raises_input_error(ws):
    with pytest.raises(R.SkillInputError, match="does not exist"):
        await handle(
            {"audio_path": "nope_missing.mp3"}, ScriptedProvider()
        )


# ---------------------------------------------------------------------------
# 2. Happy path — output validates; normalised content from the model reply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema_valid_and_normalised(ws):
    out = await handle(_valid_input(), ScriptedProvider(reply=GOOD_REPLY))

    assert R.validate_schema(_manifest().output_schema, out) == []
    assert isinstance(out["transcript"], str)
    assert isinstance(out["summary"], str) and out["summary"]
    assert out["decisions"] == ["Ship v4.4 next week"]

    items = out["action_items"]
    assert len(items) == 3
    # Every item has the required "task" key.
    assert all("task" in item for item in items)
    # Optional keys are carried through when present.
    assert items[0]["assignee"] == "Ari"
    assert items[0]["due_date"] == "2026-08-07"
    assert "assignee" not in items[1] and "due_date" not in items[1]
    # A bare-string item is normalised to {"task": ...}.
    assert items[2] == {"task": "send the minutes to the team"}


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — real context + attendees + verified file reach the LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_context_and_file_info(ws):
    provider = ScriptedProvider(events=[("token", GOOD_REPLY), ("done", None)])
    await handle(_valid_input(), provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert "Sprint 42 review" in user_prompt
    assert "Dearly" in user_prompt and "Maya" in user_prompt
    assert "meeting.mp3" in user_prompt
    assert str(len(DUMMY_AUDIO)) in user_prompt  # real byte length of the file
    # The system turn honestly pins "never fabricate a transcript".
    assert messages[0]["role"] == "system"
    assert "transcript" in messages[0]["content"]


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end(ws):
    out = await skills.execute_skill(
        "meeting_notes", _valid_input(), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["action_items"][0]["assignee"] == "Ari"


# ---------------------------------------------------------------------------
# 5. LLM failure surfaces, never swallowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_raises_runtime_error(ws):
    with pytest.raises(RuntimeError):
        await handle(_valid_input(), ScriptedProvider(fail=True))


# ---------------------------------------------------------------------------
# 6. Honest empty skeleton — schema-valid even when the model gives nothing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_model_payload_stays_schema_valid(ws):
    out = await handle(_valid_input(), ScriptedProvider(reply="{}"))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["transcript"] == ""
    assert out["action_items"] == []
    assert out["decisions"] == []
    assert out["summary"] == ""
