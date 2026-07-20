"""
Nexa Agent — TUI Application (v2.1.0)
=====================================

Full multi-pane Terminal UI for Nexa Agent, built with ``rich.live`` +
``rich.layout.Layout`` + ``prompt_toolkit``.

Layout::

    ┌─ Nexa Agent v2.1.0 │ model: gpt-4o │ tokens: ~1.2k │ server: UP │ 14:32 ─┐
    ├──────────────────────────────────────┬─────────────────────────────────────┤
    │ Chat area (scrollable, markdown)     │ Tool Log (collapsible cards)        │
    │                                      │ [🔧 read_file] ✓ 45ms               │
    ├──────────────────────────────────────┴─────────────────────────────────────┤
    │ nexa > _                                                                    │
    └─────────────────────────────────────────────────────────────────────────────┘

Features:
    - Status bar at top (model, token estimate, server status, clock).
    - Chat area in the middle (renders streaming tokens + markdown).
    - Tool log on the right (one card per tool call).
    - Input box at the bottom (prompt_toolkit with history + Shift+Enter).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rich.align import Align
from rich.console import Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nexa.constants import NEXA_NAME, NEXA_VERSION


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
@dataclass
class ChatMessage:
    """A single chat message rendered in the TUI.

    Attributes:
        role:    'user', 'assistant', or 'tool'.
        content: The message text.
        ts:      Unix timestamp.
    """
    role: str
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class ToolCallEntry:
    """A single tool-call entry rendered in the tool log pane.

    Attributes:
        name:      The tool name.
        ok:        Whether the call succeeded.
        duration_ms: Wall-clock duration in milliseconds.
        output:    Short output preview.
    """
    name: str
    ok: bool
    duration_ms: float
    output: str = ""


@dataclass
class TUIState:
    """The full mutable state of the TUI.

    Attributes:
        messages:      Chat messages (newest last).
        tool_calls:    Tool-call log entries.
        model:         Current model name.
        server_up:     Whether the gateway is up.
        streaming:     Whether the agent is currently streaming.
        token_estimate: Rough token estimate for the current turn.
    """
    messages: List[ChatMessage] = field(default_factory=list)
    tool_calls: List[ToolCallEntry] = field(default_factory=list)
    model: str = "gpt-4o"
    server_up: bool = False
    streaming: bool = False
    token_estimate: int = 0


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def _render_status_bar(state: TUIState) -> Panel:
    """Render the top status bar."""
    clock = time.strftime("%H:%M")
    server_str = "[green]UP[/green]" if state.server_up else "[red]DOWN[/red]"
    stream_str = "[yellow]…[/yellow]" if state.streaming else "[dim]idle[/dim]"
    bar = (
        f"[bold cyan]{NEXA_NAME}[/bold cyan] [dim]v{NEXA_VERSION}[/dim] │ "
        f"model: [green]{state.model}[/green] │ "
        f"tokens: [yellow]~{state.token_estimate}[/yellow] │ "
        f"server: {server_str} │ "
        f"status: {stream_str} │ "
        f"[dim]{clock}[/dim]"
    )
    return Panel(Text.from_markup(bar), height=3, border_style="cyan")


def _render_chat_area(state: TUIState) -> RenderableType:
    """Render the middle chat area (left column)."""
    if not state.messages:
        body = Align.center(
            Text(f"Hello, I'm {NEXA_NAME}. Type a message below to begin.",
                 style="dim italic")
        )
    else:
        chunks: List[RenderableType] = []
        for msg in state.messages[-20:]:  # cap to last 20 for perf
            if msg.role == "user":
                chunks.append(Text(f"You: ", style="bold blue"))
                chunks.append(Text(msg.content, style="white"))
            elif msg.role == "assistant":
                chunks.append(Text(f"{NEXA_NAME}: ", style="bold green"))
                try:
                    chunks.append(Markdown(msg.content))
                except Exception:
                    chunks.append(Text(msg.content, style="white"))
            elif msg.role == "tool":
                chunks.append(Text(f"[tool] {msg.content}", style="dim yellow"))
            chunks.append(Text(""))  # spacer
        body = Group(*chunks)
    return Panel(body, title="[cyan]Chat[/cyan]", border_style="cyan")


def _render_tool_log(state: TUIState) -> RenderableType:
    """Render the right column tool log."""
    if not state.tool_calls:
        body = Align.center(Text("No tool calls yet.", style="dim italic"))
    else:
        lines: List[RenderableType] = []
        for tc in state.tool_calls[-15:]:  # cap to last 15
            status = "[green]✓[/green]" if tc.ok else "[red]✗[/red]"
            preview = (tc.output[:80] + "…") if len(tc.output) > 80 else tc.output
            lines.append(Text.from_markup(
                f"{status} [bold]{tc.name}[/bold] [dim]({tc.duration_ms:.0f}ms)[/dim]"
            ))
            if preview:
                lines.append(Text(f"   {preview}", style="dim"))
        body = Group(*lines)
    return Panel(body, title="[cyan]Tool Log[/cyan]", border_style="cyan")


def _render_input_box(state: TUIState, current_input: str = "") -> Panel:
    """Render the bottom input box."""
    prompt = f"[bold green]nexa >[/bold green] {current_input}"
    if state.streaming:
        prompt += " [yellow]▋[/yellow]"
    return Panel(
        Text.from_markup(prompt),
        height=3,
        border_style="green",
        title="[green]Input[/green]",
    )


def build_layout(state: TUIState, current_input: str = "") -> Layout:
    """
    Build the full TUI layout for the given state.

    Args:
        state:         The current :class:`TUIState`.
        current_input: The text currently in the input box.

    Returns:
        A :class:`rich.layout.Layout` ready to render with :class:`rich.live.Live`.

    Example:
        >>> layout = build_layout(TUIState())  # doctest: +SKIP
        >>> with Live(layout, refresh_per_second=4):  # doctest: +SKIP
        ...     ...
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="chat", ratio=3),
        Layout(name="tools", ratio=2),
    )

    layout["header"].update(_render_status_bar(state))
    layout["chat"].update(_render_chat_area(state))
    layout["tools"].update(_render_tool_log(state))
    layout["footer"].update(_render_input_box(state, current_input))
    return layout


def render_snapshot(state: TUIState, current_input: str = "") -> Group:
    """
    Render a non-Live snapshot (useful for tests and non-interactive contexts).

    Args:
        state:         The current :class:`TUIState`.
        current_input: The text currently in the input box.

    Returns:
        A :class:`rich.console.Group` of all three regions stacked.
    """
    return Group(
        _render_status_bar(state),
        _render_chat_area(state),
        _render_tool_log(state),
        _render_input_box(state, current_input),
    )


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------
def add_user_message(state: TUIState, text: str) -> None:
    """Append a user message to the state."""
    state.messages.append(ChatMessage(role="user", content=text))
    state.token_estimate += len(text) // 4


def add_assistant_token(state: TUIState, token: str) -> None:
    """Append a streaming token to the current assistant message (or start one)."""
    if not state.messages or state.messages[-1].role != "assistant":
        state.messages.append(ChatMessage(role="assistant", content=token))
    else:
        state.messages[-1].content += token
    state.token_estimate += max(1, len(token) // 4)


def finalize_assistant_message(state: TUIState, full_text: str) -> None:
    """Replace the streaming assistant message with the final text."""
    if state.messages and state.messages[-1].role == "assistant":
        state.messages[-1].content = full_text
    else:
        state.messages.append(ChatMessage(role="assistant", content=full_text))


def add_tool_call(state: TUIState, entry: ToolCallEntry) -> None:
    """Append a tool-call entry to the log."""
    state.tool_calls.append(entry)


def apply_event(state: TUIState, event: Dict[str, Any]) -> None:
    """
    Apply a conversation-loop event to the TUI state.

    Recognized event types: ``thinking``, ``token``, ``tool_result``,
    ``done``, ``error``.

    Args:
        state: The TUI state to mutate.
        event: The event dict (from :func:`agent.conversation_loop.run_conversation`).
    """
    etype = event.get("type")
    if etype == "thinking":
        state.streaming = True
    elif etype == "token":
        add_assistant_token(state, event.get("text", ""))
    elif etype == "tool_result":
        result = event.get("result", {})
        add_tool_call(state, ToolCallEntry(
            name=result.get("tool", "unknown"),
            ok=result.get("ok", False),
            duration_ms=result.get("duration_ms", 0.0),
            output=str(result.get("output", ""))[:200],
        ))
    elif etype == "done":
        state.streaming = False
        finalize_assistant_message(state, event.get("answer", ""))
    elif etype == "error":
        state.streaming = False
        state.messages.append(ChatMessage(
            role="assistant", content=f"[error] {event.get('message', '')}"
        ))


# ---------------------------------------------------------------------------
# Main async loop (interactive)
# ---------------------------------------------------------------------------
async def run_tui_interactive(
    agent,
    conv_id: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Run the interactive TUI loop.

    Args:
        agent:   A :class:`run_agent.NexaAgent` instance.
        conv_id: The conversation ID for persistence.
        history: Prior messages (optional).
    """
    state = TUIState(model=getattr(agent.provider, "model", "unknown"))

    # Pre-load history into state.
    if history:
        for msg in history:
            state.messages.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
            ))

    print(f"\n{NEXA_NAME} v{NEXA_VERSION} TUI. Type 'exit' or Ctrl+C to quit.\n")

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from pathlib import Path
        hist_path = Path.home() / ".nexa" / "history"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        session = PromptSession(history=FileHistory(str(hist_path)))
    except ImportError:
        # Fallback to input() if prompt_toolkit isn't installed.
        session = None

    while True:
        try:
            if session is not None:
                user_input = await session.prompt_async("nexa > ")
            else:
                user_input = input("nexa > ")
        except (EOFError, KeyboardInterrupt):
            print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input.strip():
            continue
        if user_input.strip().lower() in ("exit", "quit", "/exit"):
            break

        add_user_message(state, user_input)
        state.streaming = True

        # Run the streaming turn.
        try:
            async for event in agent.run_streaming(user_input, conv_id, history or []):
                apply_event(state, event)
        except Exception as exc:
            state.streaming = False
            state.messages.append(ChatMessage(
                role="assistant", content=f"[error] {exc}"
            ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    """
    Entry point for the TUI (``python -m ui_tui.app``).

    Returns:
        0 on success.
    """
    import asyncio
    from run_agent import NexaAgent, set_active_agent

    agent = NexaAgent()
    set_active_agent(agent)

    async def run():
        await agent.db.init()
        conv = await agent.db.create_conversation(title="TUI session")
        await run_tui_interactive(agent, conv["id"])

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
