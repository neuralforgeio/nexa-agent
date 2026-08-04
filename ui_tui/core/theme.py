"""
Nexa Agent — TUI Theme (v4.5.0)
================================

Central colour + style tokens for the terminal UI.  All palette values are
hex strings that ``rich`` resolves at render time (the same tokens the web
frontend uses, mapped one-to-one so TUI and web feel like the same app).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Dict

# ── Semantic tokens (one accent + translucent tints, like the web) ────────────
ACCENT = "#4A9EFF"          # primary blue
ACCENT_DIM = "#2E5C9E"     # 60 %-dim variant for non-focused chrome
SUCCESS = "#4ADE80"        # ok/healthy
WARNING = "#FBBF24"        # amber for observations / memory steps
ERROR = "#F87171"          # failures / unhealthy
MUTED = "#9CA3AF"          # secondary text
FAINT = "#6B7280"          # tertiary text / hints
BORDER = "#2E2F34"        # panel borders
SURFACE = "#1A1B1E"       # modal / card body
SURFACE_HI = "#141618"    # alternate card body
BG = "#0B0C0E"            # deepest background

TEXT = "#ECECEC"

# ── Rich style-sheet (name → rich markup) ────────────────────────────────────
PALETTE: Dict[str, str] = {
    "title": f"bold {ACCENT}",
    "panel_title": f"bold {ACCENT}",
    "border": BORDER,
    "border_focus": f"bold {ACCENT}",
    "user": "bold #CCCCFF",
    "assistant": f"bold {SUCCESS}",
    "tool": f"dim {WARNING}",
    "ok": f"bold {SUCCESS}",
    "err": f"bold {ERROR}",
    "amber": WARNING,
    "muted": MUTED,
    "hint": FAINT,
    "active": f"reverse {ACCENT}",
    "table_header": f"bold {TEXT} on {SURFACE_HI}",
    "status_up": f"bold {SUCCESS}",
    "status_down": f"bold {ERROR}",
    "status_busy": f"bold {WARNING}",
}
