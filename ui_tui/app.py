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
        args:      Original JSON argument payload (v4.2.0).
    """
    name: str
    ok: bool
    duration_ms: float
    output: str = ""
    args: str = ""  # raw arguments the LLM asked for


@dataclass
class PersonaBadge:
    """
    The persona currently active in the virtual-agent state machine.

    Driven from ``agent_persona`` SSE events (or local orchestrator state).
    """

    name: str = ""
    icon: str = "🧠"
    color: str = "#9A9A9A"
    goal: str = ""


@dataclass
class WorkingProcessStep:
    """One step in the Working Process panel."""

    label: str
    ok: bool = True
    kind: str = "thinking"  # thinking | tool | observation
    detail: str = ""


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
        persona:       Active persona (or ``None``).
        working_process: Recent steps for the Working Process panel.
        sidebar_open:  Whether the tool/persona sidebar is shown (Ctrl+B).
    """
    messages: List[ChatMessage] = field(default_factory=list)
    tool_calls: List[ToolCallEntry] = field(default_factory=list)
    model: str = "gpt-4o"
    server_up: bool = False
    streaming: bool = False
    token_estimate: int = 0
    persona: Optional[PersonaBadge] = None
    working_process: List[WorkingProcessStep] = field(default_factory=list)
    sidebar_open: bool = True


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
    """Render the right column tool log.

    Each entry shows ok/fail, name, latency, the LLM-provided argument
    preview (v4.2.0), and a short output preview.
    """
    if not state.tool_calls:
        body = Align.center(Text("No tool calls yet.", style="dim italic"))
    else:
        lines: List[RenderableType] = []
        for tc in state.tool_calls[-15:]:  # cap to last 15
            status = "[green]✓[/green]" if tc.ok else "[red]✗[/red]"
            args_preview = (tc.args[:60] + "…") if tc.args and len(tc.args) > 60 else (tc.args or "")
            preview = (tc.output[:80] + "…") if len(tc.output) > 80 else tc.output
            lines.append(Text.from_markup(
                f"{status} [bold]{tc.name}[/bold] [dim]({tc.duration_ms:.0f}ms)[/dim]"
            ))
            if args_preview:
                lines.append(Text.from_markup(f"   [dim cyan]args:[/dim cyan] [dim]{args_preview}[/dim]"))
            if preview:
                lines.append(Text(f"   {preview}", style="dim"))
        body = Group(*lines)
    return Panel(body, title="[cyan]Tool Log[/cyan]", border_style="cyan")


def _render_persona_panel(state: TUIState) -> RenderableType:
    """Render the active virtual-agent persona (v4.2.0)."""
    if state.persona is None:
        return Panel(
            Align.center(Text("no persona active", style="dim italic")),
            title="[magenta]Persona[/magenta]",
            border_style="magenta",
        )
    p = state.persona
    return Panel(
        Group(
            Text(f"{p.icon} {p.name}", style="bold"),
            Text(p.goal, style="dim"),
        ),
        title="[magenta]Persona[/magenta]",
        border_style="magenta",
    )


def _render_working_process_panel(state: TUIState) -> RenderableType:
    """Render the Working-Process trace (v4.2.0)."""
    if not state.working_process:
        return Panel(
            Align.center(Text("No activity yet.", style="dim italic")),
            title="[blue]Working Process[/blue]",
            border_style="blue",
        )
    rows: List[RenderableType] = []
    for step in state.working_process[-20:]:
        icon = {"thinking": "🧠", "tool": "🔧", "observation": "👁"}.get(step.kind, "•")
        status = "[green]✓[/green]" if step.ok else "[red]✗[/red]"
        rows.append(Text(f"{icon} {status} {step.label}"))
        if step.detail:
            rows.append(Text(f"   {step.detail[:120]}", style="dim"))
    return Panel(Group(*rows), title="[blue]Working Process[/blue]", border_style="blue")


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

    # v4.2.0: the "tools" panel hosts 3 stacked sub-panes — Persona,
    # Working Process, Tool Log — and the whole right-side column can be
    # collapsed with Ctrl+B (parity with the web UI).
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
        layout["persona"].update(_render_persona_panel(state))
        layout["work"].update(_render_working_process_panel(state))
        layout["calls"].update(_render_tool_log(state))
    else:
        layout["body"].split_row(Layout(name="chat", ratio=1))

    layout["header"].update(_render_status_bar(state))
    layout["chat"].update(_render_chat_area(state))
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
    parts: List[RenderableType] = [
        _render_status_bar(state),
        _render_persona_panel(state) if state.persona else Text(""),
        _render_chat_area(state),
        _render_working_process_panel(state),
        _render_tool_log(state),
        _render_input_box(state, current_input),
    ]
    return Group(*parts)


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
    ``done``, ``error``, plus the v4.2 introspection events
    (``agent_persona``, ``patterns``, ``reflection``, ``suggestions``,
    ``confidence``, ``heal``, ``failover``, ``expand``, ``intent``,
    ``autolearn``, ``compressing``, ``memory``).

    Args:
        state: The TUI state to mutate.
        event: The event dict (from :func:`agent.conversation_loop.run_conversation`).
    """
    etype = event.get("type")
    if etype == "thinking":
        state.streaming = True
        state.working_process.append(
            WorkingProcessStep(label="thinking", detail="Model is reasoning…")
        )
    elif etype == "token":
        add_assistant_token(state, event.get("text", ""))
    elif etype == "tool_result":
        result = event.get("result", {})
        add_tool_call(state, ToolCallEntry(
            name=result.get("tool", "unknown"),
            ok=result.get("ok", False),
            duration_ms=result.get("duration_ms", 0.0),
            output=str(result.get("output", ""))[:200],
            args=str(result.get("args", ""))[:200],
        ))
        state.working_process.append(
            WorkingProcessStep(
                label=str(result.get("tool", "tool")),
                ok=bool(result.get("ok", False)),
                kind="tool",
                detail=str(result.get("output", ""))[:160],
            )
        )
    elif etype == "agent_persona":
        badge = event.get("persona", {}) or {}
        state.persona = PersonaBadge(
            name=badge.get("name", ""),
            icon=badge.get("icon", "🧠"),
            color=badge.get("color", "#9A9A9A"),
            goal=badge.get("goal", ""),
        )
        state.working_process.append(
            WorkingProcessStep(
                label=f"persona:{state.persona.name}",
                kind="observation",
                detail=state.persona.goal,
            )
        )
    elif etype == "patterns":
        state.working_process.append(
            WorkingProcessStep(label="patterns", kind="observation", detail=str(event.get("detail", ""))[:160])
        )
    elif etype == "reflection":
        state.working_process.append(
            WorkingProcessStep(label="reflection", kind="observation", detail=str(event.get("summary", ""))[:160])
        )
    elif etype == "suggestions":
        items = event.get("items", []) or []
        for it in items[:2]:
            label = it.get("label") if isinstance(it, dict) else str(it)
            state.working_process.append(
                WorkingProcessStep(label="suggestion", detail=str(label)[:160])
            )
    elif etype == "confidence":
        state.working_process.append(
            WorkingProcessStep(
                label="confidence",
                detail=f"score={event.get('score')} enrich={event.get('should_enrich')}",
            )
        )
    elif etype in ("heal", "failover", "expand", "intent", "autolearn", "compressing", "memory"):
        state.working_process.append(
            WorkingProcessStep(label=etype, kind="observation", detail=str(event.get("message") or event.get("detail") or event.get("summary") or "")[:160])
        )
    elif etype == "done":
        state.streaming = False
        state.working_process.append(
            WorkingProcessStep(label="done", kind="observation", detail="answer ready")
        )
        finalize_assistant_message(state, event.get("answer", ""))
    elif etype == "error":
        state.streaming = False
        state.working_process.append(
            WorkingProcessStep(label="error", ok=False, kind="observation", detail=str(event.get("message", ""))[:160])
        )
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

        # v3.0.0: slash-command dispatcher.
        if user_input.strip().startswith("/"):
            handled = await _handle_tui_slash_command(state, agent, user_input.strip())
            if handled:
                continue  # don't send slash command to the LLM

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


async def _handle_tui_slash_command(
    state: TUIState,
    agent: Any,
    raw: str,
) -> bool:
    """
    Handle a slash command inside the TUI.

    Returns ``True`` if the command was handled (and should NOT be sent to
    the LLM), ``False`` if it should be passed through as a normal message.

    Supported commands:
        /help, /exit, /provider [list|use|test|add|remove], /model <name>,
        /doctor (shows health summary inline).

    Args:
        state:  The current TUI state.
        agent:  The NexaAgent instance.
        raw:    The raw slash command string (e.g. ``"/provider list"``).

    Returns:
        ``True`` if handled, ``False`` to pass through.
    """
    parts = raw.split()
    cmd = parts[0].lower()
    if cmd in ("/help", "/?"):
        state.messages.append(ChatMessage(
            role="tool",
            content=(
                "TUI commands: /help, /exit, /provider [list|use <n>|test <n>|add|remove <n>], "
                "/model <name>, /doctor"
            ),
        ))
        return True
    if cmd in ("/exit", "/quit"):
        raise KeyboardInterrupt  # break the outer loop
    if cmd == "/provider":
        from nexa.provider_registry import ProviderRegistry
        reg = ProviderRegistry()
        sub = parts[1].lower() if len(parts) > 1 else ""
        if not sub or sub == "list":
            lines = ["Providers:"]
            active = reg.get_active()
            for p in reg.list_all():
                marker = "→" if active and active.name == p.name else " "
                lines.append(f"  {marker} {p.name}: {p.base_url or '(env)'} | {p.model}")
            state.messages.append(ChatMessage(role="tool", content="\n".join(lines)))
            return True
        if sub == "use" and len(parts) >= 3:
            name = parts[2]
            if reg.set_active(name):
                cfg = reg.get_active()
                if cfg:
                    agent.provider.base_url = cfg.base_url
                    agent.provider.model = cfg.model
                    agent.provider.api_key = cfg.api_key
                    agent.provider._client = None
                    state.model = cfg.model
                    state.messages.append(ChatMessage(
                        role="tool", content=f"✓ Switched to {name} ({cfg.base_url})"
                    ))
            else:
                state.messages.append(ChatMessage(
                    role="tool", content=f"✗ Unknown provider: {name}"
                ))
            return True
        if sub == "test" and len(parts) >= 3:
            name = parts[2]
            state.messages.append(ChatMessage(role="tool", content=f"Probing {name}..."))
            try:
                healthy = await reg.test(name)
                state.messages.append(ChatMessage(
                    role="tool",
                    content=f"{'✓' if healthy else '✗'} {name} {'healthy' if healthy else 'unreachable'}",
                ))
            except Exception as exc:
                state.messages.append(ChatMessage(
                    role="tool", content=f"✗ {name}: {exc}"
                ))
            return True
        if sub == "add":
            state.messages.append(ChatMessage(
                role="tool",
                content="Use 'nexa provider add' in a terminal (interactive prompts not supported in TUI).",
            ))
            return True
        if sub == "remove" and len(parts) >= 3:
            name = parts[2]
            if reg.remove(name):
                state.messages.append(ChatMessage(role="tool", content=f"✓ Removed {name}"))
            else:
                state.messages.append(ChatMessage(role="tool", content=f"✗ No such provider: {name}"))
            return True
        # Unknown /provider subcommand — show usage.
        state.messages.append(ChatMessage(
            role="tool",
            content="Usage: /provider [list|use <n>|test <n>|add|remove <n>]",
        ))
        return True
    if cmd == "/model" and len(parts) >= 2:
        agent.provider.model = parts[1]
        state.model = parts[1]
        state.messages.append(ChatMessage(role="tool", content=f"✓ Model set to {parts[1]}"))
        return True
    if cmd == "/doctor":
        try:
            from agent.self_health import SelfHealth
            from nexa.state import ConversationDB
            db = agent.db if hasattr(agent, "db") and agent.db else ConversationDB()
            health = SelfHealth(db)
            report = await health.run_full_check()
            state.messages.append(ChatMessage(
                role="tool", content=f"Health: {'ALL OK' if report.all_healthy else 'ISSUES'}"
            ))
        except Exception as exc:
            state.messages.append(ChatMessage(role="tool", content=f"✗ {exc}"))
        return True
    # Unknown slash command — let it pass through to the LLM.
    return False


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
