"""
Tests for the Persona Manager (v4.1.0).

Covers:
    - Persona catalog completeness (one persona per AgentPhase).
    - Badge shape for the chat UI (icon/name/color/goal).
    - The ``filter_registry`` allow-list (Coder must not run tests, etc.).
    - ``base_persona_block`` system-prompt segment.
    - Persona swapping as the orchestrator advances phases.
"""

from __future__ import annotations

import pytest

from agent.orchestrator import AgentPhase, new_session
from agent.persona_manager import (
    PERSONAS,
    PersonaManager,
    base_persona_block,
    persona_badge,
    persona_for_phase,
)


class TestPersonaCatalog:
    def test_every_phase_has_a_persona(self):
        for phase in AgentPhase:
            assert phase in PERSONAS, f"missing persona for {phase}"

    def test_planner_constraints(self):
        p = PERSONAS[AgentPhase.PLANNING]
        assert p.icon == "\U0001F9E0"  # 🧠
        tools = set(p.allowed_tools or [])
        assert "write_file" not in tools  # Planner must NOT write code
        assert "task_plan" in tools

    def test_reviewer_constraints(self):
        p = PERSONAS[AgentPhase.REVIEWING]
        tools = set(p.allowed_tools or [])
        assert "write_file" not in tools  # Reviewer must NOT write code
        assert "run_terminal_command" in tools

    def test_coder_has_write_tools(self):
        p = PERSONAS[AgentPhase.CODING]
        tools = set(p.allowed_tools or [])
        assert "write_file" in tools


class TestBadge:
    def test_badge_shape(self):
        b = persona_badge(AgentPhase.CODING)
        assert b["name"] == "Coder Agent"
        assert b["icon"] == "\U0001F4BB"  # 💻
        assert b["color"].startswith("#")
        assert "plan" in b["goal"].lower()

    def test_badge_fallback(self):
        # Unknown / garbage phase object that isn't in the dict → Coder.
        class _Bogus:
            pass

        b = persona_badge(_Bogus())  # type: ignore[arg-type]
        assert b["name"] == "Coder Agent"


class TestPersonaManager:
    def test_tracks_orchestrator_phase(self):
        orch = new_session()
        pm = PersonaManager(orch)
        assert pm.current_phase == AgentPhase.PLANNING
        assert pm.current_persona().name == "Planner Agent"

        orch.transition_to(AgentPhase.CODING, reason="plan cleared")
        assert pm.current_phase == AgentPhase.CODING
        assert pm.current_persona().name == "Coder Agent"

    def test_system_prompt_segment_matches_phase(self):
        orch = new_session()
        pm = PersonaManager(orch)
        assert "Planner" in pm.system_prompt_segment()
        orch.transition_to(AgentPhase.REVIEWING if False else AgentPhase.CODING)
        orch.transition_to(AgentPhase.REVIEWING)
        assert "Reviewer" in pm.system_prompt_segment()

    def test_describe_for_log(self):
        pm = PersonaManager(new_session())
        assert "Planner Agent" in pm.describe_for_log()
        assert "PLANNING" in pm.describe_for_log()


@pytest.fixture()
def registry():
    from tools.registry import create_default_registry

    return create_default_registry()


class TestFilterRegistry:
    def test_coder_whitelist(self, registry):
        orch = new_session()
        orch.transition_to(AgentPhase.CODING)
        pm = PersonaManager(orch)
        schemas = pm.filter_registry(registry)
        names = {s["function"]["name"] for s in schemas}
        assert "write_file" in names
        assert "run_terminal_command" not in names
        # Filtered list should be much smaller than the full registry.
        assert len(names) < len(registry.list_names())

    def test_reviewer_whitelist(self, registry):
        orch = new_session()
        orch.transition_to(AgentPhase.CODING)
        orch.transition_to(AgentPhase.REVIEWING)
        pm = PersonaManager(orch)
        schemas = pm.filter_registry(registry)
        names = {s["function"]["name"] for s in schemas}
        assert "run_terminal_command" in names
        assert "write_file" not in names

    def test_done_persona_unrestricted(self, registry):
        orch = new_session()
        orch._state.phase = AgentPhase.DONE
        pm = PersonaManager(orch)
        schemas = pm.filter_registry(registry)
        assert len(schemas) == len(registry.list_names())


class TestBasePersonaBlock:
    def test_block_mentions_persona(self):
        block = base_persona_block(AgentPhase.EXPLORING)
        assert "Explorer Agent" in block
        assert "Allowed tools" in block

    def test_done_block_lists_all_tools(self):
        block = base_persona_block(AgentPhase.DONE)
        assert "All registered tools are available" in block
