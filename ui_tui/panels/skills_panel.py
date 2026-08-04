"""
Nexa Agent — TUI Skills Overlay (v4.5.0)
==========================================

Renders an interactive skills panel (category chips + search + run + result)
as an overlay Panel, matching the web SettingsPanel Skills tab.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui_tui.core.theme import ACCENT, BORDER, MUTED, SUCCESS, TEXT, WARNING
from ui_tui.core.state import TUIState


# Category display labels (same as frontend). Order matters — this is the
# fixed row of chips.
_CATEGORY_LABELS: dict[str, str] = {
    "code_intelligence": "Code Intel",
    "web_research": "Web Research",
    "creative_media": "Creative",
    "communication": "Comms",
    "data_analytics": "Data",
    "devops_operations": "DevOps",
}


def _skill_row(skill: Dict[str, Any], selected: bool) -> Text:
    """Render one skill as a single-line row."""
    name = skill["name"]
    cat = skill["category"]
    desc = skill["description"]
    enabled = skill.get("enabled", True)
    marker = Text("▸", style=f"bold {ACCENT}") if selected else Text(" ")
    chip = Text(f" [{cat}]", style=WARNING)
    status = Text(" ✗", style=ERROR) if not enabled else Text()
    desc_short = desc[:70] + ("…" if len(desc) > 70 else "")
    return Text.assemble(
        marker, " ",
        Text(name, style=f"bold {TEXT}"), chip, status,
        "  ", Text(desc_short, style=MUTED),
    )


def build_skills_overlay(state: TUIState, skills: List[Dict[str, Any]], filter_text: str = "") -> Panel:
    """
    Render the skills browser as a Panel.

    Args:
        state:       Current TUI state (for enabled flag, results cache).
        skills:      All skills (from ``skills.list_skills()``).
        filter_text: Case-insensitive substring filter.

    Returns:
        A :class:`rich.panel.Panel` ready to insert into a Layout.
    """
    # Apply filter
    q = filter_text.lower().strip()
    visible = [
        s for s in skills
        if not q or q in s["name"].lower() or q in s["description"].lower()
        or any(q in t.lower() for t in s.get("tags", []))
    ]

    # Category chips
    chips: List[Text] = []
    cats = sorted({s["category"] for s in skills})
    for cat in cats:
        count = sum(1 for s in visible if s["category"] == cat)
        chip_style = f"reverse {ACCENT}" if state.skills_filter == cat else f"bold {WARNING}"
        chips.append(Text(f" {_CATEGORY_LABELS.get(cat, cat)} ({count}) ", style=chip_style))
    chip_row = Text(" ").join(chips)

    # Table
    table = Table(box=None, padding=(0, 1), show_header=True, header_style=f"bold {MUTED}")
    table.add_column("Skill", style=TEXT, no_wrap=True, max_width=35)
    table.add_column("Version", style=MUTED, no_wrap=True, justify="right")
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Category", style=WARNING)
    table.add_column("Description", style=MUTED, max_width=50)

    for i, skill in enumerate(visible):
        enabled = skill.get("enabled", True)
        status = Text("✓", style=SUCCESS) if enabled else Text("✗", style=ERROR)
        table.add_row(
            skill["name"],
            skill["version"],
            status,
            skill["category"],
            skill["description"][:50] + ("…" if len(skill["description"]) > 50 else ""),
            style=f"reverse {ACCENT}" if i == 0 and visible else "",
        )

    footer = Text(
        f" {len(visible)}/{len(skills)} shown"
        + (f"  filter: {filter_text!r}" if filter_text else "")
        + "  ·  Ctrl+B to close",
        style=MUTED,
    )

    body = Group(chip_row, Text(""), table, Text(""), footer)
    return Panel(
        body,
        title=f"[bold {ACCENT}]Skills[/bold {ACCENT}]  [dim](Ctrl+L to close)[/dim]",
        border_style=ACCENT,
        padding=(0, 1),
        height=min(len(visible) + 10, 35),
    )
