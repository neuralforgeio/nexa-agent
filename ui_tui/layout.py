"""
Nexa Agent — TUI Layout (v4.5.0)
=================================

Builds the complete ``rich.layout.Layout`` from a :class:`TUIState`.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Optional

from rich.layout import Layout

from ui_tui.renderers import (
    render_chat_area,
    render_input_box,
    render_persona,
    render_status_bar,
    render_tool_log,
    render_working_process,
)
from ui_tui.state import TUIState
from ui_tui.skills_panel import build_skills_overlay


def _footer_panel_name(state: TUIState) -> str:
    """Which panel to show in the bottom input/footer area."""
    # priority: skills overlay > input box
    if state.active_panel == "skills":
        return "skills"
    return "input"


def build_layout(state: TUIState, current_input: str = "") -> Layout:
    """
    Build the full four-panel TUI layout.

    The layout responds to:
      - ``state.sidebar_open``  → right-hand panel shown/hidden
      - ``state.active_panel``   → which panel gets focus highlight
      - ``state.skills_list``   → skills browser overlay (if non-empty)

    Returns:
        A :class:`rich.layout.Layout` ready for ``rich.live.Live``.
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    layout["header"].update(render_status_bar(state))

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------
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
        layout["chat"].update(render_chat_area(state))

    # ------------------------------------------------------------------
    # Footer: input box by default; skills overlay if active_panel == "skills"
    # ------------------------------------------------------------------
    if state.active_panel == "skills" and state.skills_list:
        layout["footer"].update(
            build_skills_overlay(state, state.skills_list, state.skills_filter)
        )
    else:
        layout["footer"].update(render_input_box(state, current_input))

    return layout
