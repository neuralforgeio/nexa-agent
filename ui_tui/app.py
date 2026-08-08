"""
Nexa Agent — TUI Application (v4.6.0)

Main entry point.  Most of the logic lives in the sub-packages:

  ui_tui.core       — state, theme, event reducer (apply_event), helpers
  ui_tui.render     — layout + panel renderers + snapshot builder
  ui_tui.input      — prompt session (NexaPromptSession) + key bindings
  ui_tui.panels     — overlay builders (skills browser)
  ui_tui.services   — background services (health poller, etc.)
  ui_tui.commands   — full slash-command dispatcher (18 commands)

This module re-exports everything as a convenience facade so both
``from ui_tui.app import ...`` (legacy) and ``from ui_tui.core.app import ...``
(new) keep working.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Group
from rich.live import Live
from rich.text import Text

from openforge.constants import NEXA_NAME, NEXA_VERSION

# ── Sub-package imports ────────────────────────────────────────────────────
from ui_tui.core.state import (
    ChatMessage,
    PersonaBadge,
    TUIState,
    ToolCallEntry,
    WorkingProcessStep,
    apply_event,
)
from ui_tui.core.theme import PALETTE, ACCENT, MUTED, SUCCESS, WARNING
from ui_tui.core.app import (
    add_user_message,
    add_assistant_token,
    add_tool_call,
    finalize_assistant_message,
)
from ui_tui.render.layout import build_layout
from ui_tui.render.panels import (
    render_chat_area,
    render_input_box,
    render_persona,
    render_status_bar,
    render_tool_log,
    render_working_process,
)
from ui_tui.input.keys import bind_state, kb
from ui_tui.input.session import NexaPromptSession
from ui_tui.panels.skills_panel import build_skills_overlay
from ui_tui.services.server_health import ServerHealthPoller

# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat re-exports (for tests + callers that use `ui_tui.app`)
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Data
    "TUIState", "ChatMessage", "ToolCallEntry", "WorkingProcessStep", "PersonaBadge",
    "apply_event",
    # Helpers
    "add_user_message", "add_assistant_token", "add_tool_call",
    "finalize_assistant_message", "main",
    # Rendering
    "build_layout",
    "render_snapshot",  # defined below (needs Panel composition)
]

# ─────────────────────────────────────────────────────────────────────────────
# Snapshot renderer (kept here because it composes across sub-packages)
# ─────────────────────────────────────────────────────────────────────────────

from rich.console import Group  # noqa: E402 — re-export for test consumers


def render_snapshot(state: TUIState, current_input: str = "") -> Group:
    """Render a non-Live snapshot of the TUI (for tests/headless contexts)."""
    return Group(
        render_status_bar(state),
        render_persona(state) if state.persona else Text(""),
        render_chat_area(state),
        render_working_process(state),
        render_tool_log(state),
        render_input_box(state, current_input),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level state bootstrap (set once per process)
# ─────────────────────────────────────────────────────────────────────────────

_state: TUIState | None = None


def _get_or_create_state(agent) -> TUIState:
    """Return the singleton TUIState for this process."""
    global _state
    if _state is None:
        _state = TUIState(
            model=getattr(agent.provider, "model", "unknown"),
            provider_name=getattr(agent, "provider_name", "unknown"),
        )
        bind_state(_state)
    return _state


# ─────────────────────────────────────────────────────────────────────────────
# Skills overlay helper
# ─────────────────────────────────────────────────────────────────────────────

async def _refresh_skills(state: TUIState) -> None:
    """Populate state.skills_list from the registry (called once)."""
    try:
        import skills
        cards = skills.list_skills()
        state.skills_list = [
            {
                "name": c["name"],
                "version": c["version"],
                "description": c["description"],
                "category": c["category"],
                "enabled": c["enabled"],
                "permissions": c.get("permissions", []),
                "tags": c.get("tags", []),
                "examples": c.get("examples", []),
            }
            for c in cards
        ]
    except Exception:
        state.skills_list = []


# ─────────────────────────────────────────────────────────────────────────────
# Main interactive loop
# ─────────────────────────────────────────────────────────────────────────────

async def run_tui(agent, conv_id: str, history: Optional[List[Dict[str, Any]]] = None) -> None:
    """
    Run the full interactive TUI.

    This wires together:
      - ``Live(build_layout(state))`` — the painted 4-panel UI
      - ``NexaPromptSession``           — multi-line input with history + patch_stdout
      - ``apply_event``                 — state reducer for 16 event types
      - ``ui_tui.commands.dispatch``   — the full slash-command set
      - ``ServerHealthPoller``          — background /api/health updates

    Args:
        agent:    A :class:`run_agent.OpenForgeAgent` instance.
        conv_id:  Conversation ID for persistence.
        history:  Prior messages to preload (optional).
    """
    state = _get_or_create_state(agent)
    state.current_session = conv_id

    # ── Start background health polling (best-effort) ─────────────────────────
    poller = None
    try:
        import os
        backend = os.environ.get("NEXA_BACKEND", "http://localhost:8000")
        poller = ServerHealthPoller(state, backend_url=backend)
        poller.start()
    except Exception:
        poller = None

    # ── Pre-load conversation history ─────────────────────────────────────────
    if history:
        for msg in history:
            state.messages.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
            ))

    # ── Load skills list lazily (used by /skills overlay and /skills tool) ──
    await _refresh_skills(state)

    # ── Create the prompt session ─────────────────────────────────────────────
    session = NexaPromptSession()
    prompt_session = session.raw_session

    with Live(
        build_layout(state),
        console=None,
        refresh_per_second=8,
        vertical_overflow="visible",
    ) as live:
        while True:
            try:
                raw = await prompt_session.prompt_async()
            except KeyboardInterrupt:
                if state.streaming:
                    state.streaming = False
                    state.turn_started_at = None
                    state.working_process.append(
                        WorkingProcessStep(label="cancelled", ok=False, kind="observation")
                    )
                    live.update(build_layout(state))
                    continue
                raise
            except EOFError:
                break

            raw = raw.strip()
            if not raw:
                continue

            # ── Skills overlay shortcut ───────────────────────────────────────
            if raw.lower() in ("/skills", "/sk"):
                state.active_panel = "skills" if state.active_panel != "skills" else "chat"
                live.update(build_layout(state))
                continue

            # ── Slash commands ────────────────────────────────────────────────
            if raw.startswith("/"):
                try:
                    from ui_tui.commands import dispatch as _dispatch_cmd
                except ImportError:
                    from ui_tui import commands as _cmd_mod
                    _dispatch_cmd = _cmd_mod.dispatch
                result = await _dispatch_cmd(state, agent, raw)
                if result:
                    state.messages.append(ChatMessage(role="tool", content=result))
                live.update(build_layout(state))
                continue

            # ── Normal chat turn ─────────────────────────────────────────────
            add_user_message(state, raw)
            state.streaming = True
            state.turn_started_at = time.time()

            # Show "thinking" immediately.
            state.working_process.append(
                WorkingProcessStep(label="reasoning", detail="Model is thinking…")
            )

            async for event in agent.run_streaming(raw, conv_id, []):
                apply_event(state, event)
                live.update(build_layout(state))

            # Final paint once everything is settled.
            state.streaming = False
            state.turn_started_at = None
            live.update(build_layout(state))

    # ── Cleanup ────────────────────────────────────────────────────────────────
    if poller is not None:
        poller.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    """TUI entry point (``nexa-tui``) — delegates to :func:`run_tui`."""
    from src.run_agent import OpenForgeAgent, set_active_agent

    agent = OpenForgeAgent()
    set_active_agent(agent)

    async def run() -> None:
        await agent.db.init()
        if hasattr(agent.db, "list_conversations"):
            convs = await agent.db.list_conversations()
            conv = convs[0] if convs else await agent.db.create_conversation(title="TUI session")
        else:
            conv = await agent.db.create_conversation(title="TUI session")
        await run_tui(agent, conv["id"])

    asyncio.run(run())
    return 0


def main_app() -> int:
    """Alias for ``main`` (some callers use this name)."""
    return main()


if __name__ == "__main__":
    import sys
    sys.exit(main())
