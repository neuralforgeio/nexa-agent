"""
Nexa Agent — Virtual Multi-Agent Orchestrator (v4.1.0)
=======================================================

Because local LLMs like llama.cpp can only run one inference slot at a
time, we emulate a multi-agent setup via a **state machine**: a single
process whose *system prompt* is swapped between phases (Planner →
Explorer → Coder → Reviewer → Done), with file-backed shared memory in
``~/.openforge/workspace/`` so phases can communicate without overflowing the
context window.

The Orchestrator is a *planner*, not a *runner*. It doesn't call tools or
the LLM directly — it produces the correct system-prompt augmentation and
tells the conversation loop which phase we should be in next. The
conversation loop wires the events; the backend persists the state so a
later turn can resume a half-finished plan.

File-backed shared memory (per ``~/.openforge/workspace/``):

- ``task.md``     — the Planner's structured plan.
- ``context.md``  — the Explorer's summary of what's already known.
- ``errors.log``  — the Reviewer's findings.
- ``state.json``  — small bookkeeping blob (phase, round, updated_at).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from openforge.config import FORGE_HOME


# ---------------------------------------------------------------------------
# Agent states
# ---------------------------------------------------------------------------
class AgentPhase(str, Enum):
    """The phases a virtual agent session cycles through."""

    PLANNING = "PLANNING"
    EXPLORING = "EXPLORING"
    CODING = "CODING"
    REVIEWING = "REVIEWING"
    DONE = "DONE"


#: Ordered transition DAG.
#:   PLANNING  → EXPLORING (needs research) | CODING (already clear)
#:   EXPLORING → CODING
#:   CODING    → REVIEWING
#:   REVIEWING → DONE (success) | CODING (failure loop, capped at 3 loops)
_TRANSITIONS: Dict[AgentPhase, List[AgentPhase]] = {
    AgentPhase.PLANNING: [AgentPhase.EXPLORING, AgentPhase.CODING],
    AgentPhase.EXPLORING: [AgentPhase.CODING],
    AgentPhase.CODING: [AgentPhase.REVIEWING],
    AgentPhase.REVIEWING: [AgentPhase.DONE, AgentPhase.CODING],
    AgentPhase.DONE: [],
}
#: How many REVIEWING→CODING loops are permitted before force-DONE.
_MAX_REVIEW_CYCLES = 3


@dataclass
class OrchestratorState:
    """
    The persistent state of the orchestrator.

    Attributes:
        phase:         The current :class:`AgentPhase`.
        round_count:   How many times we've entered REVIEWING (loop cap).
        history:       A list of ``(phase, timestamp)`` events, newest last.
        plan_path:     Workspace-relative path to ``task.md``.
        context_path:  Workspace-relative path to ``context.md``.
        errors_path:   Workspace-relative path to ``errors.log``.
    """

    phase: AgentPhase = AgentPhase.PLANNING
    round_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    plan_path: str = "task.md"
    context_path: str = "context.md"
    errors_path: str = "errors.log"


# ---------------------------------------------------------------------------
# Shared workspace helpers
# ---------------------------------------------------------------------------
_WORKSPACE_DIR = FORGE_HOME / "workspace"


def _workspace_dir() -> Path:
    """Return the shared workspace directory, creating it if needed."""
    _WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_DIR


def read_workspace_file(rel: str) -> str:
    """Read a shared-memory file, returning empty string if absent."""
    p = _workspace_dir() / rel
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def write_workspace_file(rel: str, content: str) -> Path:
    """Atomically write a shared-memory file inside ``~/.openforge/workspace/``."""
    p = _workspace_dir() / rel
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(p)
    return p


def append_workspace_file(rel: str, content: str) -> Path:
    """Append text to a shared-memory file (creating it if absent)."""
    p = _workspace_dir() / rel
    with p.open("a", encoding="utf-8") as fh:
        fh.write(content)
        if not content.endswith("\n"):
            fh.write("\n")
    return p


def read_orchestrator_state() -> OrchestratorState:
    """Load the orchestrator state from ``state.json``, or a fresh default."""
    p = _workspace_dir() / "state.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        state = OrchestratorState(
            phase=AgentPhase(raw.get("phase", AgentPhase.PLANNING.value)),
            round_count=int(raw.get("round_count", 0)),
            history=list(raw.get("history", [])),
        )
        return state
    except Exception:
        return OrchestratorState()


def save_orchestrator_state(state: OrchestratorState) -> Path:
    """Persist the orchestrator state."""
    p = _workspace_dir() / "state.json"
    data = {
        "phase": state.phase.value,
        "round_count": state.round_count,
        "history": state.history[-25:],  # keep last 25 events
        "updated_at": int(time.time()),
    }
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)
    return p


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class Orchestrator:
    """
    The state machine that routes the conversation through phases.

    The public surface is intentionally small:

    - :meth:`current_phase` — what phase are we in?
    - :meth:`decide_next` — given a phase result, pick the next phase.
    - :meth:`transition_to` — apply a validated transition (with logging).
    - :meth:`persona_prompt` — the system-prompt segment for the active phase.

    Designed for the ``conversation_loop`` to call between turns.
    """

    def __init__(
        self,
        state: Optional[OrchestratorState] = None,
        *,
        fresh: bool = False,
    ) -> None:
        """
        Initialize with persisted state (resume), a provided state, or start
        completely fresh.

        Args:
            state:  Explicit state object (skips disk load).
            fresh:  When ``True``, always start at PLANNING — ignore any
                    on-disk ``state.json`` (avoids cross-session leaks).
        """
        if fresh:
            self._state = OrchestratorState()
        else:
            self._state = state or read_orchestrator_state()
        self._persist = True

    # ------------------------------------------------------------------
    @property
    def current_phase(self) -> AgentPhase:
        """The active phase."""
        return self._state.phase

    @property
    def state(self) -> OrchestratorState:
        """The full state object (read-only access via getter)."""
        return self._state

    # ------------------------------------------------------------------
    def log_event(self, message: str) -> None:
        """Append a timestamped event to the history log."""
        self._state.history.append(
            {
                "ts": time.strftime("%H:%M:%S"),
                "phase": self._state.phase.value,
                "event": message,
            }
        )
        if self._persist:
            save_orchestrator_state(self._state)

    def transition_to(self, next_phase: AgentPhase, reason: str = "") -> None:
        """
        Validate and apply a phase transition.

        Allowed transitions are defined by :data:`_TRANSITIONS`. The only
        backward edge is ``REVIEWING → CODING``, and only while
        ``self._state.round_count < _MAX_REVIEW_CYCLES``.

        Args:
            next_phase: The phase to move into.
            reason:     Human-readable rationale (shown in the UI log).

        Raises:
            ValueError: If the requested transition is not permitted.
        """
        current = self._state.phase
        allowed = _TRANSITIONS.get(current, [])

        # Special-case: REVIEWING → CODING loops (bounded). The direct
        # transition_to path doesn't carry a phase_result, so a request to
        # re-enter CODING from REVIEWING counts as one review round; once the
        # cap is hit we force DONE instead of looping forever.
        if current == AgentPhase.REVIEWING and next_phase == AgentPhase.CODING:
            self._state.round_count += 1
            if self._state.round_count >= _MAX_REVIEW_CYCLES:
                self._state.phase = AgentPhase.DONE
                self.log_event(
                    f"Force DONE after {self._state.round_count} review loops "
                    f"(last failure reason: {reason or 'unspecified'})"
                )
                return

        if next_phase not in allowed:
            # Allow idempotent re-entry into the SAME phase (retry).
            if next_phase == current:
                self.log_event(f"Stay in {current.value} ({reason})")
                return
            raise ValueError(
                f"Illegal transition {current.value} → {next_phase.value}. "
                f"Allowed: {[p.value for p in allowed]}"
            )

        self._state.phase = next_phase
        self.log_event(f"{current.value} → {next_phase.value} ({reason})")
        if self._persist:
            save_orchestrator_state(self._state)

    # ------------------------------------------------------------------
    def decide_next(self, phase_result: Dict[str, Any]) -> AgentPhase:
        """
        Pick the next phase based on the current phase's result.

        This is the only place that inspects tool output; everything else
        in this class is pure routing.

        Args:
            phase_result: A dict with keys like ``ok``, ``wrote_plan``,
                          ``saw_error``, ``needs_research``. Every phase
                          result shape is documented per-persona below.

        Returns:
            The next :class:`AgentPhase`.
        """
        current = self._state.phase

        # PLANNING completed → EXPLORING (needs research) or CODING.
        if current == AgentPhase.PLANNING:
            needs_research = bool(phase_result.get("needs_research"))
            nxt = AgentPhase.EXPLORING if needs_research else AgentPhase.CODING
            self.transition_to(nxt, "Planner produced a task.md")
            return nxt

        # EXPLORING completed → CODING.
        if current == AgentPhase.EXPLORING:
            self.transition_to(AgentPhase.CODING, "Explorer wrote context.md")
            return AgentPhase.CODING

        # CODING completed → REVIEWING.
        if current == AgentPhase.CODING:
            self.transition_to(AgentPhase.REVIEWING, "Coder wrote files")
            return AgentPhase.REVIEWING

        # REVIEWING: on success → DONE; on failure → CODING.
        if current == AgentPhase.REVIEWING:
            saw_error = bool(phase_result.get("saw_error"))
            if saw_error:
                # transition_to() increments round_count and may force-DONE
                # at the cap. Return the ACTUAL resulting phase, not the
                # requested destination.
                self.transition_to(
                    AgentPhase.CODING, phase_result.get("error_summary", "error")
                )
                return self.current_phase
            self.transition_to(AgentPhase.DONE, "Reviewer passed")
            return AgentPhase.DONE

        return AgentPhase.DONE

    # ------------------------------------------------------------------
    def persona_prompt(self, phase: Optional[AgentPhase] = None) -> str:
        """
        Return the phase-specific system-prompt segment that augments the
        base system prompt while this phase is active.

        The segment explains what the persona is, what it is allowed to do,
        and which shared-memory files to read/write.

        Args:
            phase: The phase to describe (defaults to current).

        Returns:
            A Markdown system-prompt segment.
        """
        phase = phase or self._state.phase
        plan = f"~/.openforge/workspace/{self._state.plan_path}"
        ctx = f"~/.openforge/workspace/{self._state.context_path}"
        errors = f"~/.openforge/workspace/{self._state.errors_path}"

        if phase == AgentPhase.PLANNING:
            return (
                "# Planner Persona\n\n"
                "You are the Planner: decompose the user's goal into a clear, "
                "step-ordered plan. Do NOT write production code. Do NOT call "
                "build/run commands. Your only deliverables are:\n"
                f"- Write `{plan}` (stepping stones, file paths, acceptance criteria)\n"
                f"- Write `{ctx}` (why this is a good approach — short)\n"
                "- Return `needs_research: true` if you do not yet understand the workspace.\n"
                "\n"
                "Sign off with: \"Plan written. Moving to CODING.\""
            )
        if phase == AgentPhase.EXPLORING:
            return (
                "# Explorer Persona\n\n"
                "You are the Explorer: gather the facts the Coder will need. "
                "You may read files and search the web. You must NOT write or "
                "edit production code. Deliverables:\n"
                f"- Update `{ctx}` with your findings\n"
                "- Return when you can say \"Context ready.\""
            )
        if phase == AgentPhase.CODING:
            return (
                "# Coder Persona\n\n"
                "You are the Coder: implement the plan from "
                f"`{plan}`, consulting `{ctx}`. "
                "ONLY call `write_file` and `code_execution`. Do NOT run shells "
                "or tests (the Reviewer will). When done, say \"Code ready for "
                "review.\""
            )
        if phase == AgentPhase.REVIEWING:
            return (
                "# Reviewer Persona\n\n"
                "You are the Reviewer: run tests/builds (via `run_terminal_command`) "
                f"and analyze stderr. If anything fails, append a minimal error report to `{errors}` "
                "and set `saw_error: true`. On success, declare DONE.\n"
                "\n"
                "Do NOT write production code. You ONLY run commands and read output."
            )
        return (
            "# Final Reporter\n\n"
            "You are the Final Reporter: summarize what was achieved, which "
            "files changed, and any follow-up suggestions. Be brief."
        )


# ---------------------------------------------------------------------------
# Convenience APIs used by the conversation loop / tests
# ---------------------------------------------------------------------------
def new_session(task_hint: str = "") -> Orchestrator:
    """Start a fresh orchestrator session (resets state + history)."""
    state = OrchestratorState()
    return Orchestrator(state=state)
