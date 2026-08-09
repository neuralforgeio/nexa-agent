"""
OpenForge — TUI State + Event Reducer (v4.5.0)
=================================================

The single source of truth for the TUI's mutable state, plus
:func:`apply_event` — the reducer that converts every `run_streaming` event
into visible state changes.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Value objects
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ChatMessage:
    """One conversational message rendered in the chat pane."""
    role: str          # "user" | "assistant" | "tool"
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class ToolCallEntry:
    """One tool invocation, summarised for the tool-log pane."""
    name: str
    ok: bool
    duration_ms: float
    output: str = ""
    args: str = ""


@dataclass
class PersonaBadge:
    """The active virtual-agent persona (orchestrator state)."""
    name: str = ""
    icon: str = "🧠"
    color: str = "#9A9A9A"
    goal: str = ""


@dataclass
class WorkingProcessStep:
    """One step in the Working-Process trace."""
    label: str
    ok: bool = True
    kind: str = "thinking"   # thinking | tool | observation
    detail: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Main state container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TUIState:
    """All mutable state for the TUI.

    Panels read from it; they never write.  Mutations happen via explicit
    helpers (``add_user_message`` etc.) or the ``apply_event`` reducer.
    """

    # Conversation
    messages: List[ChatMessage] = field(default_factory=list)
    tool_calls: List[ToolCallEntry] = field(default_factory=list)
    token_estimate: int = 0

    # Infrastructure
    model: str = "gpt-4o"
    provider_name: str = "unknown"
    server_up: bool = False
    streaming: bool = False
    turn_started_at: Optional[float] = None

    # Orchestrator / introspection
    persona: Optional[PersonaBadge] = None
    working_process: List[WorkingProcessStep] = field(default_factory=list)

    # UI chrome
    sidebar_open: bool = True
    active_panel: str = "chat"   # chat | tools | skills | sessions

    # Skills panel
    skills_list: List[Dict[str, Any]] = field(default_factory=list)
    skills_filter: str = ""

    # Sessions panel
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    current_session: str = ""

    # Input
    pending_slash: Optional[str] = None   # last slash command echo
    last_render_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------
    # UI helpers (no rendering — pure state transitions)
    # ------------------------------------------------------------

    def elapsed_turn(self) -> float:
        """Seconds since the current turn started (0 if idle)."""
        if self.turn_started_at is None:
            return 0.0
        return time.time() - self.turn_started_at

    def status_summary(self) -> str:
        """Compact status line for the header."""
        parts = [
            f"{self.provider_name}:{self.model}",
            f"~{self.token_estimate}tok",
            "UP" if self.server_up else "DOWN",
        ]
        if self.streaming:
            parts.append("⣿ streaming")
        return " │ ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Event reducer — maps each run_streaming event to state mutations
# ─────────────────────────────────────────────────────────────────────────────

def apply_event(state: TUIState, event: Dict[str, Any]) -> None:
    """
    Route one conversation-loop event into TUI state.

    This is the TUI's *event bus reducer*: it knows about every event
    ``run_conversation`` can fire (16 types), and updates the state in a way
    the renderers can consume immediately.
    """
    etype = event.get("type")

    if etype == "thinking":
        state.streaming = True
        state.turn_started_at = time.time()
        state.working_process.append(
            WorkingProcessStep(label="reasoning", detail="Model is thinking…")
        )

    elif etype == "token":
        token = event.get("text", "")
        if not state.messages or state.messages[-1].role != "assistant":
            state.messages.append(ChatMessage(role="assistant", content=""))
        state.messages[-1].content += token
        state.token_estimate += max(1, len(token) // 4)

    elif etype == "tool_result":
        result = event.get("result", {})
        state.tool_calls.append(
            ToolCallEntry(
                name=result.get("tool", "unknown"),
                ok=result.get("ok", False),
                duration_ms=result.get("duration_ms", 0.0),
                output=str(result.get("output", ""))[:200],
                args=str(result.get("args", ""))[:200],
            )
        )
        state.working_process.append(
            WorkingProcessStep(
                label=str(result.get("tool", "tool")),
                ok=bool(result.get("ok", False)),
                kind="tool",
                detail=str(result.get("output", ""))[:160],
            )
        )

    elif etype == "agent_persona":
        badge = event.get("persona", {}) or {}
        state.persona = PersonaBadge(
            name=badge.get("name", ""),
            icon=badge.get("icon", "🧠"),
            color=badge.get("color", "#9A9A9A"),
            goal=badge.get("goal", ""),
        )
        state.working_process.append(
            WorkingProcessStep(
                label=f"persona:{state.persona.name}",
                kind="observation",
                detail=state.persona.goal,
            )
        )

    elif etype == "patterns":
        state.working_process.append(
            WorkingProcessStep(
                label="patterns",
                kind="observation",
                detail=str(event.get("detail", ""))[:160],
            )
        )

    elif etype == "reflection":
        state.working_process.append(
            WorkingProcessStep(
                label="reflection",
                kind="observation",
                detail=str(event.get("summary", ""))[:160],
            )
        )

    elif etype == "suggestions":
        items = event.get("items", []) or []
        for it in items[:2]:
            label = it.get("label") if isinstance(it, dict) else str(it)
            state.working_process.append(
                WorkingProcessStep(label="suggestion", detail=str(label)[:160])
            )

    elif etype == "confidence":
        state.working_process.append(
            WorkingProcessStep(
                label="confidence",
                detail=f"score={event.get('score')} enrich={event.get('should_enrich')}",
            )
        )

    elif etype in ("heal", "failover", "expand", "intent", "autolearn", "compressing", "memory"):
        state.working_process.append(
            WorkingProcessStep(
                label=etype,
                kind="observation",
                detail=str(
                    event.get("message") or event.get("detail") or event.get("summary") or ""
                )[:160],
            )
        )

    elif etype == "done":
        state.streaming = False
        state.turn_started_at = None
        state.working_process.append(
            WorkingProcessStep(label="done", kind="observation", detail="answer ready")
        )
        final_text = event.get("answer", "")
        if state.messages and state.messages[-1].role == "assistant":
            state.messages[-1].content = final_text
        else:
            state.messages.append(ChatMessage(role="assistant", content=final_text))

    elif etype == "error":
        state.streaming = False
        state.turn_started_at = None
        state.working_process.append(
            WorkingProcessStep(
                label="error",
                ok=False,
                kind="observation",
                detail=str(event.get("message", ""))[:160],
            )
        )
        state.messages.append(
            ChatMessage(role="assistant", content=f"[error] {event.get('message', '')}")
        )


__all__ = [
    "TUIState",
    "ChatMessage",
    "ToolCallEntry",
    "PersonaBadge",
    "WorkingProcessStep",
    "apply_event",
]
