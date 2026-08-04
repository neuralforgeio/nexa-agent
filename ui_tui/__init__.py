"""
Nexa Agent — TUI Package (v4.6.0)
===================================

Backward-compat shim: keeps ``from ui_tui import X`` working while the real
code lives under sub-packages:

  ui_tui.core      — state, theme, event reducer, application loop
  ui_tui.render    — layout + panel renderers
  ui_tui.input     — prompt session + key bindings
  ui_tui.panels    — overlay builders (skills)
  ui_tui.services  — background services (health poller)
  ui_tui.commands  — slash-command dispatcher

New code should import from the sub-packages (``ui_tui.core.state``);
``ui_tui.app`` → ``ui_tui.core.app``, etc.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

# Re-export the public surface so `from ui_tui import X` keeps working.
from ui_tui.core.state import (
    ChatMessage,
    PersonaBadge,
    TUIState,
    ToolCallEntry,
    WorkingProcessStep,
    apply_event,
)
from ui_tui.core.theme import PALETTE, ACCENT, ACCENT_DIM, BG, BORDER, MUTED, SUCCESS, WARNING

from ui_tui.render.layout import build_layout
from ui_tui.render.panels import (
    render_chat_area,
    render_input_box,
    render_persona,
    render_status_bar,
    render_tool_log,
    render_working_process,
)

from ui_tui.input.keys import bind_state, cycle_active_panel, kb, toggle_sidebar
from ui_tui.input.session import NexaPromptSession, make_prompt_style

from ui_tui.panels.skills_panel import build_skills_overlay

from ui_tui.services.server_health import ServerHealthPoller

__all__ = [
    # State
    "ChatMessage", "PersonaBadge", "TUIState", "ToolCallEntry", "WorkingProcessStep",
    "apply_event",
    # Theme
    "PALETTE", "ACCENT", "ACCENT_DIM", "BG", "BORDER", "MUTED", "SUCCESS", "WARNING",
    # Render
    "build_layout", "render_chat_area", "render_input_box", "render_persona",
    "render_status_bar", "render_tool_log", "render_working_process",
    # Input
    "bind_state", "cycle_active_panel", "kb", "toggle_sidebar",
    "NexaPromptSession", "make_prompt_style",
    # Panels
    "build_skills_overlay",
    # Services
    "ServerHealthPoller",
]
