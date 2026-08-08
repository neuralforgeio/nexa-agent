"""
Nexa Agent — TUI Renderers (v4.5.0)
====================================

Every ``_render_*`` function takes a :class:`TUIState` and returns a
:class:`rich` renderable.  No state mutation happens here.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from rich.align import Align
from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from openforge.constants import NEXA_NAME, NEXA_VERSION, NEXA_AUTHOR

from ui_tui.core.theme import PALETTE, ACCENT, ACCENT_DIM, BG, BORDER, ERROR
from ui_tui.core.theme import TEXT, MUTED, SUCCESS, SURFACE, SURFACE_HI, WARNING
from ui_tui.core.state import (
    ChatMessage,
    PersonaBadge,
    TUIState,
    ToolCallEntry,
    WorkingProcessStep,
)


# ---------------------------------------------------------------------------
# Header / status bar
# ---------------------------------------------------------------------------

def render_status_bar(state: TUIState) -> Panel:
    """The 3-line top bar: identity + provider/model + server + clock."""
    clock = time.strftime("%H:%M:%S")
    server = (
        Text("● UP", style=PALETTE["status_up"])
        if state.server_up
        else Text("● DOWN", style=PALETTE["status_down"])
    )
    busy = (
        Text(" ⣿ streaming", style=WARNING)
        if state.streaming
        else Text(" idle", style=MUTED)
    )
    tok = Text(f"[yellow]~{state.token_estimate}[/yellow] tok")

    # Persona capsule (if active)
    persona_txt = Text("")
    if state.persona:
        persona_txt = Text(f" {state.persona.icon} {state.persona.name}", style=PALETTE["muted"])

    bar = Group(
        Text.assemble(
            (f" {NEXA_NAME} ", f"bold {ACCENT}"),
            (f" v{NEXA_VERSION} ", "dim"),
            (f" by {NEXA_AUTHOR} ", "dim"),
        ),
        Text.assemble(
            Text(" model:", style=MUTED),
            Text(f" {state.model}", style=f"bold {TEXT}"),
            Text("  provider:", style=MUTED),
            Text(f" {state.provider_name}", style=MUTED),
            Text("  tokens:", style=MUTED),
            Text(f" ~{state.token_estimate}", style=MUTED),
            persona_txt,
        ),
        Text.assemble(
            server,
            busy,
            Text(f"  {clock}", style=MUTED),
        ),
    )
    return Panel(
        bar,
        height=5,
        border_style=ACCENT_DIM,
        padding=(0, 1),
        title="[dim]nexa-tui[/dim]",
    )


# ---------------------------------------------------------------------------
# Chat area
# ---------------------------------------------------------------------------

_MAX_CHAT_VISIBLE = 30


def render_chat_area(state: TUIState) -> Panel:
    """Scrollable chat messages with streaming support."""
    if not state.messages:
        body = Align.center(
            Text(
                f"Hello, I'm {NEXA_NAME}.\nType a message below to begin.",
                style=MUTED,
                justify="center",
            )
        )
    else:
        chunks: List[RenderableType] = []
        for msg in state.messages[-_MAX_CHAT_VISIBLE:]:
            if msg.role == "user":
                chunks.append(Text(f"\nYou", style=f"bold {TEXT}"))
                chunks.append(Text(msg.content, style=TEXT))
            elif msg.role == "assistant":
                chunks.append(Text(f"\n{NEXA_NAME}", style=PALETTE["assistant"]))
                try:
                    chunks.append(Markdown(msg.content))
                except Exception:
                    chunks.append(Text(msg.content, style=TEXT))
            elif msg.role == "tool":
                chunks.append(Text(f"[tool] {msg.content}", style=PALETTE["tool"]))
        body = Group(*chunks)
    return Panel(
        body,
        title="[dim]Chat[/dim]",
        border_style=BORDER,
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Working Process (thinking/tool trace)
# ---------------------------------------------------------------------------


def _step_icon(kind: str, ok: bool) -> Text:
    if kind == "tool":
        return Text.from_markup(f"{'[green]✓[/green]' if ok else '[red]✗[/red]'} 🔧")
    if kind == "observation":
        return Text.from_markup(f"{'[green]✓[/green]' if ok else '[red]✗[/red]'} 👁")
    # thinking
    return Text.from_markup("[blue]🧠[/blue]")


_MAX_WP_VISIBLE = 15


def render_working_process(state: TUIState) -> Panel:
    """The agent's working-process trace (thoughts + tools + observations)."""
    if not state.working_process:
        body = Align.center(Text("No activity yet.", style=MUTED))
    else:
        rows: List[RenderableType] = []
        for step in state.working_process[-_MAX_WP_VISIBLE:]:
            icon = _step_icon(step.kind, step.ok)
            rows.append(Group(
                icon,
                Text(f" {step.label}", style=TEXT),
            ))
            if step.detail:
                rows.append(Text(f"   {step.detail[:160]}", style=MUTED))
        body = Group(*rows)
    return Panel(
        body,
        title="[dim]Working Process[/dim]",
        border_style=BORDER,
        padding=(0, 1),
        height=min(len(state.working_process) + 4, 12),
    )


# ---------------------------------------------------------------------------
# Tool log
# ---------------------------------------------------------------------------

_MAX_TOOL_VISIBLE = 12


def render_tool_log(state: TUIState) -> Panel:
    """Recent tool invocations with latency and output preview."""
    if not state.tool_calls:
        body = Align.center(Text("No tool calls yet.", style=MUTED))
    else:
        rows: List[RenderableType] = []
        for tc in state.tool_calls[-_MAX_TOOL_VISIBLE:]:
            # ── One-liner: icon + name + latency
            icon = Text.from_markup("[green]✓[/green]" if tc.ok else "[red]✗[/red]")
            name = Text(tc.name, style=f"bold {WARNING}")
            dur = Text(f" ({tc.duration_ms:.0f}ms)", style=MUTED)
            header = Text.assemble(icon, name, dur)
            rows.append(header)

            # ── Expanded details (dropdown)
            if state.persona and state.persona.detail_open:
                rows.append(Text(f"   args: {tc.args[:200]}"))
                preview = tc.output[:300]
                if len(tc.output) > 300:
                    preview += "…"
                rows.append(Text(f"   {preview}", style="dim"))
        body = Group(*rows)
    return Panel(
        body,
        title="[dim]Tool Log[/dim]",
        border_style=BORDER,
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Persona panel
# ---------------------------------------------------------------------------


def render_persona(state: TUIState) -> Panel:
    """The orchestrator's currently-active virtual agent."""
    if state.persona is None:
        body = Align.center(Text("no persona active", style=MUTED))
    else:
        p = state.persona
        body = Group(
            Text(f"{p.icon} {p.name}", style=f"bold {p.color}"),
            Text(p.goal or "—", style=MUTED),
        )
    return Panel(
        body,
        title="[dim]Persona[/dim]",
        border_style=BORDER,
        padding=(0, 1),
        height=6,
    )


# ---------------------------------------------------------------------------
# Input box
# ---------------------------------------------------------------------------


def render_input_box(state: TUIState, current_input: str = "") -> Panel:
    """The composable input field."""
    prompt_txt = Text()
    if state.streaming:
        prompt_txt.append("⣿ ", style=f"bold {WARNING}")
    prompt_txt.append(f"{NEXA_NAME} > ", style=f"bold {SUCCESS}")
    prompt_txt.append(current_input, style=TEXT)
    prompt_txt.append(" ", style=MUTED)
    prompt_txt.append("(Ctrl+T tools · Ctrl+P persona · Tab cycle panels)", style=MUTED)
    return Panel(
        prompt_txt,
        height=3,
        border_style=SUCCESS,
        padding=(0, 1),
        title="[dim]Input[/dim]",
    )
