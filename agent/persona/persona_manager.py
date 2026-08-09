"""
OpenForge — Persona Manager (v4.1.0)
======================================

Swaps the active persona (Planner / Explorer / Coder / Reviewer / Final
Reporter) based on the orchestrator's current phase. Each persona comes
with:

  - a **system-prompt segment** (``Orchestrator.persona_prompt(phase)``)
    injected into the LLM's system message,
  - a **badge** for the chat UI so the user can see which persona is
    driving the current turn,
  - an **allowed-tools whitelist** (e.g. the Coder persona can call
    ``write_file`` but must not run tests).

Because local providers run one inference slot at a time, only ONE
persona is active per turn. This is by design (see
``agent/orchestrator.py``): the state machine decides which persona
wakes up next.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openforge.constants import (
    NEXA_NAME
)

from .orchestrator import AgentPhase, Orchestrator


# ---------------------------------------------------------------------------
# Persona schema
# ---------------------------------------------------------------------------
@dataclass
class Persona:
    """
    A virtual agent persona.

    Attributes:
        name:        Display label (e.g. "Planner Agent").
        icon:        Emoji icon shown in the chat UI badge.
        color:       Accent color (CSS hex) for the badge.
        phase:       The orchestrator phase this persona runs.
        allowed_tools: Tools this persona is allowed to call (whitelist).
                     ``None`` = no restriction (tools may still be limited
                     by the underlying model's capability).
        goal:        One-line description of what the persona is trying to do.
    """

    name: str
    icon: str
    color: str
    phase: AgentPhase
    allowed_tools: Optional[List[str]]  # None = unrestricted
    goal: str


# ---------------------------------------------------------------------------
# Persona catalog
# ---------------------------------------------------------------------------
PERSONAS: Dict[AgentPhase, Persona] = {
    AgentPhase.PLANNING: Persona(
        name="Planner Agent",
        icon="🧠",
        color="#A78BFA",
        phase=AgentPhase.PLANNING,
        allowed_tools=["task_plan", "todo_write", "todo_read", "scratchpad_write", "think"],
        goal="Decompose the user's goal into an ordered, dependency-aware plan.",
    ),
    AgentPhase.EXPLORING: Persona(
        name="Explorer Agent",
        icon="🔍",
        color="#FBBF24",
        phase=AgentPhase.EXPLORING,
        allowed_tools=[
            "read_file", "list_directory", "search_files", "file_info",
            "web_search", "web_fetch", "memory_search", "session_search",
            "scratchpad_write", "think",
        ],
        goal="Gather the facts the Coder needs; never modify production code.",
    ),
    AgentPhase.CODING: Persona(
        name="Coder Agent",
        icon="💻",
        color="#4A9EFF",
        phase=AgentPhase.CODING,
        allowed_tools=[
            "write_file", "file_patch", "revert_file", "read_file",
            "project_scaffold", "scratchpad_write", "think",
        ],
        goal="Implement the plan from the Planner persona, byte-for-byte.",
    ),
    AgentPhase.REVIEWING: Persona(
        name="Reviewer Agent",
        icon="🛡️",
        color="#4ADE80",
        phase=AgentPhase.REVIEWING,
        allowed_tools=[
            "run_terminal_command", "terminal_exec", "read_file",
            "list_background_processes", "kill_background_process",
            "think",
        ],
        goal="Run tests/builds and analyze the resulting output. Report pass/fail.",
    ),
    AgentPhase.DONE: Persona(
        name="Final Reporter",
        icon="✅",
        color="#4ADE80",
        phase=AgentPhase.DONE,
        allowed_tools=None,  # no tool restriction — this is just a summary
        goal="Tell the user what was achieved and what's next.",
    ),
}


def persona_for_phase(phase: AgentPhase) -> Persona:
    """Return the Persona for a given phase (falls back to Coder)."""
    return PERSONAS.get(phase, PERSONAS[AgentPhase.CODING])


def persona_badge(phase: AgentPhase) -> Dict[str, Any]:
    """
    Return a UI-ready badge dict for the current phase.

    Used by the web frontend to render the small pill that identifies
    which virtual agent is speaking (e.g. ``🧠 Planner Agent``).
    """
    p = persona_for_phase(phase)
    return {"name": p.name, "icon": p.icon, "color": p.color, "goal": p.goal}


class PersonaManager:
    """
    Drives persona swaps for a single conversation turn.

    Wraps an :class:`Orchestrator` and supplies:
      1. The injected system-prompt segment for the active phase.
      2. A UI badge descriptor so the chat can render which persona is live.
      3. The allowed-tools whitelist to filter the registry.
    """

    def __init__(self, orchestrator: Optional[Orchestrator] = None) -> None:
        """Attach to an orchestrator (creates a fresh one if absent)."""
        self._orch = orchestrator or Orchestrator()

    @property
    def orchestrator(self) -> Orchestrator:
        return self._orch

    @property
    def current_phase(self) -> AgentPhase:
        return self._orch.current_phase

    def current_persona(self) -> Persona:
        return persona_for_phase(self._orch.current_phase)

    def badge(self) -> Dict[str, Any]:
        return persona_badge(self._orch.current_phase)

    # ------------------------------------------------------------------
    # Integration points used by the conversation loop
    # ------------------------------------------------------------------
    def system_prompt_segment(self) -> str:
        """Return the persona's system-prompt segment for the active phase."""
        return self._orch.persona_prompt(self._orch.current_phase)

    def filter_registry(self, registry) -> "list":
        """
        Return tool schemas filtered by the current persona's allow-list.

        If the persona has no whitelist (``allowed_tools is None``), all
        schemas pass through unchanged. Otherwise only schemas whose
        function name appears in ``allowed_tools`` are kept.

        Args:
            registry: A :class:`tools.registry.ToolRegistry` whose
                      ``get_openai_schemas()`` yields the full tool catalog.

        Returns:
            A filtered list of OpenAI function schemas.
        """
        schemas = registry.get_openai_schemas()
        whitelist = self.current_persona().allowed_tools
        if whitelist is None:
            return schemas
        keep = set(whitelist)
        return [s for s in schemas if s.get("function", {}).get("name") in keep]

    def describe_for_log(self) -> str:
        """Return a one-line log blurb for the current phase."""
        p = self.current_persona()
        return f"{p.icon} {p.name} (phase={self._orch.current_phase.value}) — {p.goal}"


# ---------------------------------------------------------------------------
# Helper: identity line for the shared system prompt
# ---------------------------------------------------------------------------
def base_persona_block(phase: AgentPhase) -> str:
    """
    Return the identity block included at the TOP of the system prompt so
    the model knows *who* is speaking even if the phase section is far below.

    Example return::

        ---
        ## Active Persona: 💻 Coder Agent
        You are the Coder Agent. Implement the plan from the Planner persona.
        ---
    """
    p = persona_for_phase(phase)
    goal = p.goal.rstrip(".") + "."
    tools_note = (
        f"Allowed tools: {', '.join(p.allowed_tools)}."
        if p.allowed_tools
        else "All registered tools are available."
    )
    return (
        "---\n"
        f"## Active Persona: {p.icon} {p.name}\n"
        f"{goal}\n"
        f"{tools_note}\n"
        "---"
    )
