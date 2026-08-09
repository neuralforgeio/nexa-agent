"""
OpenForge — TUI Layout (v4.6.0)
=================================

Builds the complete ``rich.layout.Layout`` from a :class:`TUIState`.

Panels::

  ┌─ header ───────────────────────────────────────────┐
  │  OpenForge v4.6.0 — provider:model — ~N tok — ● UP │
  ├─ body ─────────────────────────────────────────────┤
  │  Chat                          Tools / Persona      │
  ├─ footer ───────────────────────────────────────────┤
  │  input box  │  /palette dropdown  │  skills panel   │
  └─────────────────────────────────────────────────────┘

The footer switches between three modes depending on what's active:
  - ``current_input`` starts with ``/`` → palette dropdown
  - ``state.active_panel == "skills"``  → skills overlay
  - otherwise                            → plain input box

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Optional

from rich.layout import Layout

from ui_tui.core.state import TUIState
from ui_tui.panels.skills_panel import build_skills_overlay
from ui_tui.render.panels import (
    render_chat_area,
    render_input_box,
    render_persona,
    render_status_bar,
    render_tool_log,
    render_working_process,
)
from ui_tui.render.palette import build_command_palette


def build_layout(state: TUIState, current_input: str = "") -> Layout:
    """
    Build the full four-panel TUI layout.

    Responds to:
      - ``state.sidebar_open``     — right panel shown/hidden
      - ``state.active_panel``      — which panel gets focus highlight
      - ``current_input``           — when starts with "/", palette dropdown appears
      - ``state.skills_filter``   — skills overlay visible when non-empty

    Returns:
        A :class:`rich.layout.Layout` ready for ``rich.live.Live``.
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )

    # ── Header
    layout["header"].update(render_status_bar(state))

    # ── Body
    if state.sidebar_open:
        layout["body"].split_row(
            Layout(name="chat", ratio=3),
            Layout(name="tools", ratio=2),
        )
        layout["tools"].split_column(
            Layout(name="persona", size=6),
            Layout(name="work", ratio=2),
            Layout(name="calls", ratio=2),
        )
        layout["persona"].update(render_persona(state))
        layout["work"].update(render_working_process(state))
        layout["calls"].update(render_tool_log(state))
    else:
        layout["body"].split_row(Layout(name="chat", ratio=1))

    # ── Footer (priority: command palette > skills overlay > input)
    typed = (current_input or "").strip()
    if typed.startswith("/"):
        layout["footer"].update(build_command_palette(typed))
        layout["footer"].name = "palette"
    elif state.active_panel == "skills" and state.skills_list:
        layout["footer"].update(build_skills_overlay(state, state.skills_list, state.skills_filter))
        layout["footer"].name = "skills"
    else:
        layout["footer"].update(render_input_box(state, current_input))
        layout["footer"].name = "input"

    return layout