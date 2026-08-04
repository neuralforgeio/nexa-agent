"""
Tests for the ``diagram_generation`` skill handler.

The provider is a :class:`tests._skill_helpers.ScriptedProvider` — a scripted
stand-in for the LLM boundary only. Prompt construction, schema validation,
and the registry executor all run for real.

Honesty invariant under test: ``diagram_code`` must be the model's real reply
to a prompt that embeds the *actual* description, and ``rendered_url`` must
honestly be ``""`` — no renderer is configured, so no URL is fabricated.
"""

from __future__ import annotations

import pytest

import skills
from skills import registry as R
from skills.creative_media.diagram_generation.handler import handle
from tests._skill_helpers import ScriptedProvider

DESCRIPTION = (
    "user submits a request, gateway authenticates, orchestrator routes to a skill"
)

GOOD_REPLY = (
    "sequenceDiagram\n"
    "    participant U as User\n"
    "    participant G as Gateway\n"
    "    participant O as Orchestrator\n"
    "    U->>G: submit request\n"
    "    G->>G: authenticate\n"
    "    G->>O: route to skill\n"
)

EMPTY_INPUT: dict = {"description": DESCRIPTION, "diagram_type": "sequence", "format": "mermaid"}


def _manifest():
    return skills.get_skill("diagram_generation").manifest


# ---------------------------------------------------------------------------
# 1. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_description_raises_input_error():
    with pytest.raises(R.SkillInputError):
        await handle(
            {"diagram_type": "sequence", "format": "mermaid"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_bad_diagram_type_raises_input_error():
    with pytest.raises(R.SkillInputError, match="diagram_type"):
        await handle(
            {**EMPTY_INPUT, "diagram_type": "mindmap"}, ScriptedProvider()
        )


@pytest.mark.asyncio
async def test_bad_format_raises_input_error():
    with pytest.raises(R.SkillInputError, match="format"):
        await handle({**EMPTY_INPUT, "format": "dot"}, ScriptedProvider())


# ---------------------------------------------------------------------------
# 2. Happy path + schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_schema():
    out = await handle(EMPTY_INPUT, ScriptedProvider(reply=GOOD_REPLY))
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["diagram_code"].startswith("sequenceDiagram")
    assert "orchestrator" in out["diagram_code"].lower()
    # Honest: no renderer is configured, so no URL is fabricated.
    assert out["rendered_url"] == ""


# ---------------------------------------------------------------------------
# 3. Prompt fidelity — the real description reached the provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_real_description():
    provider = ScriptedProvider(reply=GOOD_REPLY)
    await handle(EMPTY_INPUT, provider)

    assert len(provider.calls) == 1
    messages = provider.calls[0]
    user_prompt = provider.last_user_message(messages)
    assert DESCRIPTION in user_prompt
    assert "sequence" in user_prompt
    assert "mermaid" in user_prompt
    assert messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# 4. Full executor path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skill_end_to_end():
    out = await skills.execute_skill(
        "diagram_generation", dict(EMPTY_INPUT), ScriptedProvider(reply=GOOD_REPLY)
    )
    assert isinstance(out, dict)
    assert R.validate_schema(_manifest().output_schema, out) == []
    assert out["diagram_code"].startswith("sequenceDiagram")


# ---------------------------------------------------------------------------
# 5. LLM failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_propagates_runtime_error():
    with pytest.raises(RuntimeError):
        await handle(EMPTY_INPUT, ScriptedProvider(fail=True))
