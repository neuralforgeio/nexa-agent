"""
Tests for the virtual multi-agent orchestrator (v4.1.0).

Covers the full state machine: PLANNING → EXPLORING → CODING → REVIEWING →
DONE, with the REVIEWING→CODING retry loop. Matches the ACTUAL public API
in agent/orchestrator.py (current_phase, state, history, log_event,
transition_to, persona_prompt).
"""

from __future__ import annotations

import pytest

from agent.persona.orchestrator import AgentPhase, Orchestrator, new_session


@pytest.fixture
def fresh_orch():
    """A fresh orchestrator that does NOT leak state between tests."""
    orch = new_session()
    orch._persist = False  # isolate tests from the real state.json on disk
    yield orch


class TestStateMachine:
    def test_initial_phase_is_planning(self, fresh_orch):
        assert fresh_orch.current_phase == AgentPhase.PLANNING

    def test_valid_transition_path(self, fresh_orch):
        # PLANNING -> CODING -> REVIEWING -> DONE
        fresh_orch.transition_to(AgentPhase.CODING, reason="cleared")
        assert fresh_orch.current_phase == AgentPhase.CODING
        fresh_orch.transition_to(AgentPhase.REVIEWING, reason="code written")
        assert fresh_orch.current_phase == AgentPhase.REVIEWING
        fresh_orch.transition_to(AgentPhase.DONE, reason="tests pass")
        assert fresh_orch.current_phase == AgentPhase.DONE

    def test_invalid_transition_raises(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        with pytest.raises(ValueError):
            fresh_orch.transition_to(AgentPhase.PLANNING)  # back-edge not allowed

    def test_idempotent_transition_is_noop(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        before = len(fresh_orch.state.history)
        fresh_orch.transition_to(AgentPhase.CODING, reason="retry")
        assert fresh_orch.current_phase == AgentPhase.CODING
        assert len(fresh_orch.state.history) == before + 1
        assert "Stay in" in fresh_orch.state.history[-1]["event"]

    def test_review_loop_bounces_to_coding(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        fresh_orch.transition_to(AgentPhase.CODING, reason="SyntaxError")
        assert fresh_orch.current_phase == AgentPhase.CODING
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        fresh_orch.transition_to(AgentPhase.DONE)
        assert fresh_orch.current_phase == AgentPhase.DONE

    def test_cycles_force_done(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        # Each REVIEWING -> CODING increments round_count; cap = 3.
        fresh_orch.transition_to(AgentPhase.CODING)  # round 1
        assert fresh_orch.state.round_count == 1
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        fresh_orch.transition_to(AgentPhase.CODING)  # round 2
        assert fresh_orch.state.round_count == 2
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        fresh_orch.transition_to(AgentPhase.CODING)  # round 3 -> cap -> DONE
        assert fresh_orch.current_phase == AgentPhase.DONE
        assert fresh_orch.state.round_count == 3

    def test_force_done_logs_event(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        for _ in range(3):  # CODING -> REVIEWING -> (loop) CODING, 3 rounds
            fresh_orch.transition_to(AgentPhase.REVIEWING)
            fresh_orch.transition_to(AgentPhase.CODING)
        assert fresh_orch.current_phase == AgentPhase.DONE
        assert any("Force DONE" in (e.get("event") or "") for e in fresh_orch.state.history)

    def test_decide_next_review_error_increments_round(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING)
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        nxt = fresh_orch.decide_next({"saw_error": True, "error_summary": "boom"})
        assert nxt == AgentPhase.CODING
        assert fresh_orch.state.round_count == 1
        # Success path still goes DONE without touching round_count.
        fresh_orch.transition_to(AgentPhase.REVIEWING)
        nxt2 = fresh_orch.decide_next({"saw_error": False})
        assert nxt2 == AgentPhase.DONE
        assert fresh_orch.state.round_count == 1

    def test_decide_next_returns_actual_phase_when_cap_hit(self, fresh_orch):
        """BUG P0-AGENT-1: decide_next returned CODING while state was DONE."""
        fresh_orch.transition_to(AgentPhase.CODING)
        # Drive 3 REVIEWING→CODING loops via decide_next.
        for i in range(3):
            fresh_orch.transition_to(AgentPhase.REVIEWING)
            result = fresh_orch.decide_next({"saw_error": True, "error_summary": f"fail {i+1}"})
            # The returned phase MUST match the actual phase.
            assert result == fresh_orch.current_phase, (
                f"loop {i+1}: returned {result} but actual is {fresh_orch.current_phase}"
            )
        # After 3 loops we must be DONE.
        assert fresh_orch.current_phase == AgentPhase.DONE

    def test_history_uses_log_event(self, fresh_orch):
        fresh_orch.transition_to(AgentPhase.CODING, reason="initial")
        fresh_orch.transition_to(AgentPhase.REVIEWING, reason="ready to review")
        ev = fresh_orch.state.history
        assert any("PLANNING" in (e.get("event") or "") or "planning" in (e.get("event") or "").lower() for e in ev)
        assert any("CODING" in (e.get("event") or "").upper() or "current_phase" in e for e in ev[-2:])


class TestPersonaPrompt:
    def test_each_phase_persona_mentions_workspace_files(self, fresh_orch):
        for phase in (AgentPhase.PLANNING, AgentPhase.EXPLORING, AgentPhase.CODING, AgentPhase.REVIEWING):
            p = fresh_orch.persona_prompt(phase)
            assert p and len(p) > 50, f"empty persona for {phase}"
            assert "workspace/" in p.lower() or "Persona" in p

    def test_planner_forbidden_to_code(self, fresh_orch):
        p = fresh_orch.persona_prompt(AgentPhase.PLANNING)
        assert "Do NOT write production code" in p

    def test_coder_allowed_scope(self, fresh_orch):
        p = fresh_orch.persona_prompt(AgentPhase.CODING)
        # Coder explicitly mentions the files it writes + the allowed tools.
        assert "write_file" in p and "code_execution" in p

    def test_reviewer_forbidden_to_code(self, fresh_orch):
        p = fresh_orch.persona_prompt(AgentPhase.REVIEWING)
        assert "Do NOT write production code" in p


class TestWorkspace:
    def test_workspace_files_round_trip(self, tmp_path):
        """write_workspace_file and read_workspace_file work end-to-end."""
        from agent.persona.orchestrator import read_workspace_file, write_workspace_file

        write_workspace_file("task.md", "# Task\nBuild the thing.")
        write_workspace_file("context.md", "# Context\nExisting code: src/")
        assert "Build the thing" in read_workspace_file("task.md")
        assert "Existing code" in read_workspace_file("context.md")

    def test_workspace_append(self, tmp_path):
        import agent.persona.orchestrator as orch_mod

        write = orch_mod.write_workspace_file("pending.md", "first line")
        orch_mod.append_workspace_file("pending.md", "second line")
        content = orch_mod.read_workspace_file("pending.md")
        assert "first line" in content
        assert "second line" in content
