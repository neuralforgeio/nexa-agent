"""
OpenForge — Command Palette (v4.6.0)
======================================

OpenCode-style command palette shown when the user types ``/``.

Displays a compact dropdown above the input box with:
  - matching slash commands (name + description)
  - fuzzy highlight of the typed prefix
  - footer with tab-completion hints

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import List, Optional

from rich.table import Table
from rich.text import Text

from ui_tui.core.theme import ACCENT, BORDER, MUTED, TEXT, WARNING


# ---------------------------------------------------------------------------
# Command catalog — (name, description) for the palette
# ---------------------------------------------------------------------------

_PALETTE_COMMANDS: List[tuple] = [
    ("/help",       "Show all commands and usage"),
    ("/exit",       "Quit the TUI"),
    ("/quit",       "Alias for /exit"),
    ("/new",        "Start a new conversation"),
    ("/clear",      "Clear chat + tool/working panels"),
    ("/history",    "Show recent messages (last 5)"),
    ("/sessions",   "List/switch/delete conversations"),
    ("/export",     "Export session as Markdown to workspace"),
    ("/doctor",     "Run self-health checks"),
    ("/provider",   "Manage LLM providers (list/use/test/add/remove)"),
    ("/model",      "Set active LLM model"),
    ("/tools",      "List all 40 skills by category"),
    ("/skills",     "Open the skills browser overlay"),
    ("/memory",     "Add a memory entry"),
    ("/memories",   "List memory entries"),
    ("/persona",    "Show current persona + goal"),
    ("/reflect",    "Ask the agent to reflect on its last answer"),
    ("/patterns",   "Show conversation-pattern stats"),
    ("/knowledge",  "Knowledge cache entry count"),
    ("/config",     "Show config.yaml keys"),
    ("/search",     "Search workspace files (semantic)"),
]


def build_command_palette(query: str = "") -> Table:
    """
    Build a compact commands dropdown for the given typed prefix.

    Args:
        query: The partial command the user has typed so far (e.g. ``"se"``).

    Returns:
        A :class:`rich.table.Table` — one row per matching command.
    """
    q = query.lower().lstrip("/")
    if not q:
        matches = _PALETTE_COMMANDS
    else:
        matches = [c for c in _PALETTE_COMMANDS if q in c[0].lower()]

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("cmd", style=f"bold {ACCENT}", no_wrap=True)
    table.add_column("desc", style=MUTED, max_width=60)

    for name, desc in matches:
        table.add_row(name, desc)

    if not matches:
        table.add_row("[dim]no matching commands[/dim]", "")

    # Footer hint
    footer = Text(
        f" {len(matches)} match{'es' if len(matches) != 1 else ''}"
        f"{'' if q else ' — type / to filter'}"
        "  ·  [Tab] to complete  [Esc] to dismiss",
        style=MUTED,
    )
    return table  # footer appended by the caller as a Text below the table
