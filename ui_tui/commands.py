"""
OpenForge — TUI Commands (v4.5.0)
=====================================

Standalone slash-command dispatcher for the TUI.

Separated from app.py so the table of commands can be imported and exercised
by tests directly without a running Live loop.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ui_tui.core.state import TUIState, ChatMessage


# ---------------------------------------------------------------------------
# Individual command implementations
# ---------------------------------------------------------------------------


async def cmd_help(state: TUIState, agent, parts: List[str]) -> str:
    """Full help text."""
    return """TUI Commands (always type /help to show this):

  Chat
    /new                     new conversation (same window)
    /clear                   clear chat area + tool/log panels

  Sessions
    /sessions list           list sessions (Today/Yesterday/Older)
    /sessions new            create new session
    /sessions switch <id>    switch to existing session
    /sessions delete <id>    delete session

  Memory
    /memories                list memory entries (first 20)
    /memory add <text>       save a memory
    /memory del <id>         delete a memory by id

  Agent
    /persona                 current persona + goal
    /model <name>            switch LLM model
    /reflect                 reflect on last assistant answer
    /patterns                count conversation patterns
    /knowledge               knowledge cache entry count

  Tools / Skills
    /tools                   list all 40 skills
    /skills                  open skills browser overlay
    /skill info <name>         show manifest for one skill
    /skill exec <name> [json]  execute a skill with JSON input

  System
    /doctor                  run self-health checks
    /provider list           list providers
    /provider use <name>     activate a provider
    /provider test <name>    health-check a provider
    /config                  show config.yaml keys

  Export
    /export <session_id>     export session transcript to .md in workspace

  Other
    /exit                    quit TUI
    /quit                    same as /exit

  Keyboard shortcuts
    Ctrl+B  toggle sidebar (tools/persona panel)
    Ctrl+L  toggle skills overlay
    Ctrl+T  toggle tools panel
    Ctrl+P  toggle persona panel
    Tab     cycle focus between panels
    Shift+Enter  multiline input
"""


async def cmd_sessions(state: TUIState, agent, parts: List[str]) -> str:
    """Session management."""
    if len(parts) < 2:
        return (
            "Usage: /sessions [list|new|switch <id>|delete <id>]\n"
            "Current: " + (state.current_session[:8] or "-")
        )
    sub = parts[1].lower()

    if sub == "list":
        convs = await agent.db.list_conversations()
        if not convs:
            return "No conversations yet."
        lines = []
        for c in convs[:20]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(c.get("created_at", 0)))
            lines.append(f"  {c['id'][:8]}  {c.get('title','-')[:40]:40}  {c.get('message_count',0)} msgs  {ts}")
        return "Sessions:\n" + "\n".join(lines)

    if sub == "new":
        conv = await agent.db.create_conversation(title=f"TUI session {time.strftime('%H:%M')}")
        state.current_session = conv["id"]
        state.messages = []
        state.tool_calls = []
        state.working_process = []
        return f"✓ New session {conv['id'][:8]}"

    if sub == "switch" and len(parts) >= 3:
        conv_id = parts[2]
        msgs = await agent.db.get_messages(conv_id)
        if not msgs:
            return f"Session {conv_id[:8]} not found."
        state.messages = [
            ChatMessage(role=m["role"], content=m["content"]) for m in msgs
        ]
        state.current_session = conv_id
        return f"✓ Switched to {conv_id[:8]} ({len(msgs)} messages)"

    if sub == "delete" and len(parts) >= 3:
        conv_id = parts[2]
        await agent.db.delete_conversation(conv_id)
        if state.current_session == conv_id:
            state.current_session = ""
            state.messages = []
        return f"✓ Deleted {conv_id[:8]}"

    return "Unknown /sessions subcommand."


async def cmd_memory(state: TUIState, agent, parts: List[str]) -> str:
    """Memory management."""
    if len(parts) < 2:
        return "Usage: /memory [list|add <text>|del <id>]"
    sub = parts[1].lower()

    if sub == "list":
        try:
            from agent.memory import MemoryManager
            mem = MemoryManager()
            entries = await mem.list_all()
            if not entries:
                return "No memories."
            lines = [f"  {e['id'][:8]} · {e['text'][:70]}" for e in entries[:20]]
            return f"Memories ({len(entries)}):\n" + "\n".join(lines)
        except Exception as exc:
            return f"/memory list error: {exc}"

    if sub == "add" and len(parts) >= 3:
        text = " ".join(parts[2:])
        try:
            from agent.memory import MemoryManager
            mem = MemoryManager()
            entry = await mem.add(text)
            return f"✓ Memory saved (id: {entry['id'][:8]})"
        except Exception as exc:
            return f"/memory add error: {exc}"

    if sub == "del" and len(parts) >= 3:
        mid = parts[2]
        try:
            from agent.memory import MemoryManager
            mem = MemoryManager()
            await mem.delete(mid)
            return f"✓ Memory {mid[:8]} deleted"
        except Exception as exc:
            return f"/memory del error: {exc}"

    return "Unknown /memory subcommand."


async def cmd_model(state: TUIState, agent, parts: List[str]) -> str:
    """Switch LLM model."""
    if len(parts) < 2:
        return f"Current model: {state.model}"
    new_model = parts[1]
    agent.provider.model = new_model
    state.model = new_model
    return f"✓ Model set to {new_model}"


async def cmd_doctor(state: TUIState, agent, parts: List[str]) -> str:
    """Self-health check."""
    try:
        from agent.core.self_health import SelfHealth
        db = agent.db if hasattr(agent, "db") else None
        health = SelfHealth(db)
        report = await health.run_full_check()
        body = f"ALL OK" if report.all_healthy else "ISSUES FOUND"
        lines = [f"Health: {body}"]
        for check in report.checks[:10]:
            icon = "✓" if check.get("ok") else "✗"
            lines.append(f"  {icon} {check.get('name', '?')}: {check.get('detail', '')}")
        return "\n".join(lines)
    except Exception as exc:
        return f"/doctor error: {exc}"


async def cmd_provider(state: TUIState, agent, parts: List[str]) -> str:
    """Provider management."""
    from openforge.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    sub = parts[1].lower() if len(parts) > 1 else "list"

    if sub == "list":
        lines = ["Providers:"]
        active = reg.get_active()
        for p in reg.list_all():
            marker = "→" if active and active.name == p.name else " "
            lines.append(f"  {marker} {p.name}: {p.base_url or '(env)'} | {p.model}")
        return "\n".join(lines)

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
                state.provider_name = name
                return f"✓ Switched to {name} ({cfg.base_url})"
        return f"✗ Unknown provider: {name}"

    if sub == "test" and len(parts) >= 3:
        name = parts[2]
        try:
            healthy = await reg.test(name)
            return f"{'✓' if healthy else '✗'} {name} {'healthy' if healthy else 'unreachable'}"
        except Exception as exc:
            return f"✗ {name}: {exc}"

    return "Unknown /provider subcommand."


async def cmd_tools(state: TUIState, agent, parts: List[str]) -> str:
    """Show the 40 skills."""
    try:
        import skills
        cards = skills.list_skills()
        if not cards:
            return "No skills loaded."
        lines = [f"  {c['name']}  [{c['category']}]  v{c['version']}" for c in cards]
        return f"Skills ({len(cards)}):\n" + "\n".join(lines)
    except Exception as exc:
        return f"/tools error: {exc}"


async def cmd_config(state: TUIState, agent, parts: List[str]) -> str:
    """Show config."""
    try:
        import yaml
        p = Path("config.yaml")
        if not p.exists():
            return "config.yaml not found in current directory."
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        lines = [f"  {k}" for k in cfg.keys()]
        return f"Config ({p.resolve()}):\n" + "\n".join(lines)
    except Exception as exc:
        return f"/config error: {exc}"


async def cmd_persona(state: TUIState, agent, parts: List[str]) -> str:
    """Show current persona."""
    if state.persona:
        return f"{state.persona.icon} {state.persona.name}\nGoal: {state.persona.goal}"
    return "No persona active yet (orchestrator hasn't assigned one)."


async def cmd_history(state: TUIState, agent, parts: List[str]) -> str:
    """Show recent messages."""
    recent = state.messages[-5:]
    if not recent:
        return "No messages yet."
    return "\n".join(
        f"[{m.role}] {m.content[:80]}" for m in recent
    )


async def cmd_clear(state: TUIState, agent, parts: List[str]) -> str:
    """Clear the chat area."""
    state.messages = []
    state.tool_calls = []
    state.working_process = []
    state.token_estimate = 0
    return ""


async def cmd_exit(state: TUIState, agent, parts: List[str]) -> str:
    """Request TUI termination (``/exit`` or ``/quit``).

    Sets ``state.quit_requested``; the app loop breaks on it after dispatch.
    """
    state.quit_requested = True
    return ""


async def cmd_new(state: TUIState, agent, parts: List[str]) -> str:
    """Start a new conversation."""
    conv = await agent.db.create_conversation(title=f"TUI session {time.strftime('%H:%M')}")
    state.current_session = conv["id"]
    state.messages = []
    state.tool_calls = []
    state.working_process = []
    return f"✓ New conversation {conv['id'][:8]}"


async def cmd_reflect(state: TUIState, agent, parts: List[str]) -> str:
    """Reflect on the last assistant message."""
    if not state.messages:
        return "Nothing to reflect on."
    last = state.messages[-1]
    if last.role != "assistant":
        return "Last message is not from assistant."
    state.messages.append(
        ChatMessage(role="tool", content=f"Reflecting on: {last.content[:200]}")
    )
    return ""


async def cmd_patterns(state: TUIState, agent, parts: List[str]) -> str:
    """Count patterns seen."""
    n = len([s for s in state.working_process if s.kind == "observation"])
    return f"Patterns observed: {n}"


async def cmd_knowledge(state: TUIState, agent, parts: List[str]) -> str:
    """Knowledge cache."""
    try:
        from agent.learning.knowledge_cache import KnowledgeCache
        kc = KnowledgeCache()
        # Try common method names
        count = 0
        for attr in ("list", "all", "entries"):
            fn = getattr(kc, attr, None)
            if callable(fn):
                result = fn() if asyncio.iscoroutinefunction(fn) else fn()
                if asyncio.iscoroutine(result):
                    result = await result
                count = len(result)
                break
        return f"Knowledge cache entries: {count}"
    except Exception as exc:
        return f"/knowledge error: {exc}"


async def cmd_export(state: TUIState, agent, parts: List[str]) -> str:
    """Export session as markdown."""
    if len(parts) < 2:
        if state.current_session:
            return f"Usage: /export <session_id> — current: {state.current_session[:8]}"
        return "Usage: /export <session_id>"
    sid = parts[1]
    try:
        msgs = await agent.db.get_messages(sid)
        md = "# Forge Session Export\n\n"
        for m in msgs:
            ts = time.strftime("%H:%M:%S", time.localtime(m.get("created_at", time.time())))
            md += f"**{m['role'].upper()} [{ts}]**\n{m['content']}\n\n"
        ws = Path(getattr(agent, "workspace_root", Path.cwd()))
        out = ws / f"session-{sid[:8]}.md"
        out.write_text(md, encoding="utf-8")
        return f"✓ Exported to {out}"
    except Exception as exc:
        return f"/export error: {exc}"


async def cmd_search(state: TUIState, agent, parts: List[str]) -> str:
    """Search workspace files."""
    if len(parts) < 2:
        return "Usage: /search <query>"
    query = " ".join(parts[1:])
    try:
        from tools.search_files import search_files
        results = await search_files(query, max_results=5)
        if not results:
            return f"No results for: {query}"
        lines = [f"  {r}" for r in results[:5]]
        return f"Search results:\n" + "\n".join(lines)
    except Exception as exc:
        return f"/search error: {exc}"


async def cmd_skills(state: TUIState, agent, parts: List[str]) -> str:
    """Toggle the skills overlay (handled by app.py TUI loop, not here)."""
    # The overlay is triggered by the TUI loop itself, not the slash handler.
    # We just set a flag so the renderer can see it.
    state.skills_filter = ""   # reset filter
    state.skills_list = []     # will be lazily loaded by the renderer
    return ""


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "/help": cmd_help, "/?": cmd_help,
    "/sessions": cmd_sessions,
    "/memory": cmd_memory, "/memories": lambda s,a,p: cmd_memory(s,a,["memory","list"]),
    "/model": cmd_model,
    "/doctor": cmd_doctor,
    "/provider": cmd_provider,
    "/tools": cmd_tools,
    "/config": cmd_config,
    "/persona": cmd_persona,
    "/history": cmd_history,
    "/clear": cmd_clear,
    "/new": cmd_new,
    "/reflect": cmd_reflect,
    "/patterns": cmd_patterns,
    "/knowledge": cmd_knowledge,
    "/export": cmd_export,
    "/search": cmd_search,
    "/skills": cmd_skills,
    "/exit": cmd_exit,
    "/quit": cmd_exit,
}


async def dispatch(state: TUIState, agent, raw: str) -> str:
    """
    Dispatch a slash command.

    Returns:
        A string to display as a tool message (may be empty string for self-
        render commands like /clear or /skills), or None to pass through to the LLM.
    """
    parts = raw.split()
    if not parts:
        return ""
    cmd = parts[0].lower()

    fn = _DISPATCH.get(cmd)
    if fn is None:
        return ""

    return await fn(state, agent, parts)


__all__ = ["dispatch"]
