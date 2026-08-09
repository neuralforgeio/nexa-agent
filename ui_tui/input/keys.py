"""
OpenForge — TUI Keyboard Bindings (v4.5.0)
=============================================

Keyboard shortcuts for the TUI, built on ``prompt_toolkit.key_binding.KeyBindings``.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from prompt_toolkit.key_binding import KeyBindings

from ui_tui.core.state import TUIState

kb = KeyBindings()


def toggle_sidebar(state: TUIState) -> None:
    """Ctrl+B — toggle the tools/persona sidebar."""
    state.sidebar_open = not state.sidebar_open


def cycle_active_panel(state: TUIState) -> None:
    """Tab — cycle the focused panel."""
    order = ["chat", "tools", "work", "persona"]
    idx = order.index(state.active_panel) if state.active_panel in order else -1
    state.active_panel = order[(idx + 1) % len(order)]


# Wire the bindings — state is read from a module-level closure so keys can
# reach it without any global import gymnastics.
_state_ref: Optional[TUIState] = None


def bind_state(state: TUIState) -> None:
    """Inject the live TUIState so key bindings can mutate it."""
    global _state_ref
    _state_ref = state


@kb.add("c-b")
def _ctrl_b(event) -> None:
    if _state_ref is not None:
        toggle_sidebar(_state_ref)
        event.app.invalidate()


@kb.add("tab")
def _tab(event) -> None:
    if _state_ref is not None:
        cycle_active_panel(_state_ref)
        event.app.invalidate()


@kb.add("escape", "enter")
def _shift_enter(event) -> None:
    """Shift+Enter inserts a newline without submitting."""
    event.current_buffer.insert_text("\n")
