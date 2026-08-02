"""
Nexa Agent — Interactive TUI (prompt_toolkit + rich)
====================================================

This module implements the interactive terminal UI for Nexa Agent, inspired
by Claude Code.

Features:
    - Multiline input with prompt_toolkit (Shift+Enter for newline).
    - Streaming token rendering with rich markdown.
    - Tool-call visualization (collapsible cards with rich panels).
    - Slash commands (/help, /clear, /model, /provider, /history, /exit).
    - Conversation history (FileHistory at ~/.nexa/history).
    - Ctrl+C interrupt support.

Run with::

    python cli.py
    python cli.py --provider ollama --model llama3.2

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import asyncio
import os
import sys

# Bootstrap UTF-8 stdio FIRST (before any rich imports that may print).
from nexa import bootstrap as nexa_bootstrap  # noqa: F401

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from agent.core.self_health import SelfHealth
from nexa.constants import NEXA_AUTHOR, NEXA_NAME, NEXA_VERSION
from providers.catalog import list_providers, resolve_provider
from src.run_agent import NexaAgent
from nexa.state import ConversationDB

console = Console()

#: Available slash commands.
SLASH_COMMANDS = {
    "/help": "Show all commands and providers",
    "/tools": "Show all available tools with their schemas",
    "/search": "Search past conversations (FTS5 full-text). Usage: /search <query>",
    "/sessions": "List all sessions. Usage: /sessions [switch <id>]",
    "/export": "Export current session as markdown. Usage: /export [filename]",
    "/config": "Show or edit config. Usage: /config [show|set <key> <value>]",
    "/clear": "Clear the current conversation and start fresh",
    "/model": "Show or change the current model",
    "/provider": "Show or change the LLM provider",
    "/history": "Show conversation history",
    "/memories": "Show accumulated agent memories (learning store)",
    "/memory": "Show memory files (MEMORY.md + USER.md). Usage: /memory [show|sync]",
    "/doctor": "Run self-health diagnostics",
    "/persona": "Show the adaptive persona state (v2.0)",
    "/knowledge": "Show cached learned facts (v2.0). Usage: /knowledge [clear]",
    "/patterns": "Show recognized conversation patterns (v2.0)",
    "/reflect": "Reflect on the last turn (v2.0 self-improvement)",
    "/exit": "Exit Nexa Agent (or press Ctrl+D)",
}


def print_banner() -> None:
    """Print the Nexa Agent ASCII banner and version info."""
    banner = f"""
╔══════════════════════════════════════════╗
║   {NEXA_NAME} v{NEXA_VERSION}                ║
║   by {NEXA_AUTHOR:<30} ║
╚══════════════════════════════════════════╝
"""
    console.print(Panel(banner.strip(), border_style="cyan", title="[cyan]Nexa Agent[/cyan]"))
    console.print("[dim]Type your message and press Enter. Type /help for commands.[/dim]\n")


def print_help(agent: NexaAgent) -> None:
    """
    Print available slash commands and current provider info.

    Args:
        agent: The active :class:`NexaAgent` instance.
    """
    console.print(Panel("[bold]Commands[/bold]", border_style="cyan"))
    for cmd, desc in SLASH_COMMANDS.items():
        console.print(f"  [cyan]{cmd:<12}[/cyan] [dim]{desc}[/dim]")
    console.print()
    console.print(Panel("[bold]Providers[/bold]", border_style="cyan"))
    for p in list_providers():
        marker = "→" if p.base_url == agent.provider.base_url else " "
        console.print(f"  {marker} [green]{p.name:<12}[/green] [dim]{p.description}[/dim]")
    console.print(f"\n[dim]Current: provider=[green]{agent.provider.base_url}[/green] model=[green]{agent.provider.model}[/green]\n")


def _print_tools(agent: NexaAgent) -> None:
    """
    Display all registered tools with their names, descriptions, and parameter
    schemas in a rich-formatted table.

    Args:
        agent: The active :class:`NexaAgent` instance with a tool registry.
    """
    from rich.table import Table

    table = Table(title="🛠️  Nexa Agent Tools", border_style="cyan", show_lines=True)
    table.add_column("Tool", style="cyan bold", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="dim")

    for schema in agent.registry.get_openai_schemas():
        fn = schema["function"]
        name = fn["name"]
        desc = fn["description"][:80] + ("…" if len(fn["description"]) > 80 else "")
        params = fn["parameters"]
        props = params.get("properties", {})
        required = set(params.get("required", []))

        if not props:
            param_str = "[dim](none)[/dim]"
        else:
            parts = []
            for pname, pinfo in props.items():
                ptype = pinfo.get("type", "any")
                req = " *" if pname in required else ""
                parts.append(f"[cyan]{pname}[/cyan]({ptype}{req})")
            param_str = ", ".join(parts)

        table.add_row(name, desc, param_str)

    console.print(table)
    console.print(f"\n[dim]{len(agent.registry.list_names())} tools available. "
                  f"The agent can call any of these via function-calling.[/dim]\n")


async def handle_slash_command(cmd: str, agent: NexaAgent, db: ConversationDB) -> bool:
    """
    Handle a slash command. Returns True if the app should continue.

    Args:
        cmd:   The slash command string (e.g. ``"/help"``).
        agent: The active agent.
        db:    The conversation database.

    Returns:
        ``False`` if the app should exit, ``True`` to continue.
    """
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    if command == "/exit":
        return False
    if command == "/help":
        print_help(agent)
    elif command == "/tools":
        _print_tools(agent)
    elif command == "/search":
        if not arg:
            console.print("[yellow]Usage:[/yellow] /search <query>\n")
        else:
            from agent.memory.session_search import search_sessions, format_search_results
            results = await search_sessions(db, arg, limit=10)
            if not results:
                console.print(f"[dim]No results for '{arg}'.[/dim]\n")
            else:
                console.print(Panel(f"[bold]🔍 Search: '{arg}'[/bold] ({len(results)} conversations)", border_style="cyan"))
                for i, r in enumerate(results, 1):
                    snippet = r["snippet"].replace("<<", "[").replace(">>", "]")
                    console.print(
                        f"  [cyan]{i}.[/cyan] [bold]{r['title'][:50]}[/bold] "
                        f"[dim]({r['match_count']} matches)[/dim]"
                    )
                    console.print(f"     [dim]{snippet[:120]}[/dim]")
                console.print()
    elif command == "/clear":
        console.clear()
        print_banner()
    elif command == "/model":
        if arg:
            agent.provider.model = arg
            console.print(f"[green]Model set to:[/green] {arg}\n")
        else:
            console.print(f"[green]Current model:[/green] {agent.provider.model}\n")
    elif command == "/provider":
        # v4.1.0: extended /provider command with list/use/add/remove/test subcommands.
        # Backward compat: `/provider <name>` still switches to a catalog provider.
        from nexa.provider_registry import ProviderRegistry, StoredProviderConfig
        reg = ProviderRegistry()
        parts = (arg or "").split()
        sub = parts[0].lower() if parts else ""
        if not arg:
            # Show current + list.
            active = reg.get_active()
            console.print(Panel(
                f"Active: [green]{active.name if active else 'none'}[/green]\n"
                f"base_url: [cyan]{agent.provider.base_url}[/cyan]\n"
                f"model:    [green]{agent.provider.model}[/green]",
                border_style="cyan", title="[cyan]Current Provider[/cyan]",
            ))
            console.print("[dim]Usage: /provider list | /provider use <name> | /provider add | /provider remove <name> | /provider test <name> | /provider <catalog-name>[/dim]\n")
        elif sub == "list":
            all_providers = reg.list_all()
            from rich.table import Table
            table = Table(title="LLM Providers", show_header=True, header_style="bold cyan")
            table.add_column("Name", style="cyan")
            table.add_column("Base URL", style="white")
            table.add_column("Model", style="green")
            table.add_column("Key", style="dim")
            active = reg.get_active()
            for p in all_providers:
                marker = "→" if active and active.name == p.name else " "
                table.add_row(f"{marker} {p.name}", p.base_url or "(env)", p.model or "(default)", p.api_key or "(env)")
            console.print(Panel(table, border_style="cyan"))
            console.print()
        elif sub == "use" and len(parts) >= 2:
            name = parts[1]
            if reg.set_active(name):
                cfg = reg.get_active()
                if cfg:
                    agent.provider.base_url = cfg.base_url
                    agent.provider.model = cfg.model
                    agent.provider.api_key = cfg.api_key
                    agent.provider._client = None
                    console.print(f"[green]✓ Switched to[/green] {name} ({cfg.base_url})\n")
            else:
                console.print(f"[red]Unknown provider:[/red] {name}. Try /provider list\n")
        elif sub == "add":
            # Defer to nexa_cli _cmd_provider for the interactive logic.
            from nexa_cli.main import _cmd_provider
            console.print("[cyan]Add a new provider. Press Ctrl+C to abort.[/cyan]")
            try:
                rc = _cmd_provider("add")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[red]Aborted.[/red]\n")
                rc = 1
            if rc == 0:
                console.print("[green]Provider added.[/green] Use /provider list to see it.\n")
        elif sub == "remove" and len(parts) >= 2:
            name = parts[1]
            if reg.remove(name):
                console.print(f"[green]✓ Removed[/green] {name}\n")
            else:
                console.print(f"[red]No such provider:[/red] {name}\n")
        elif sub == "test" and len(parts) >= 2:
            name = parts[1]
            console.print(f"[cyan]Probing[/cyan] {name}...")
            try:
                healthy = await reg.test(name)
            except Exception as exc:
                console.print(f"[red]✗ Health check failed:[/red] {exc}\n")
                healthy = False
            if healthy:
                console.print(f"[green]✓ {name} is healthy.[/green]\n")
            else:
                console.print(f"[red]✗ {name} is unreachable.[/red]\n")
        else:
            # Backward compat: /provider <name> for known catalog names.
            base_url, model, api_key = resolve_provider(arg)
            agent.provider.base_url = base_url
            agent.provider.model = model
            agent.provider.api_key = api_key
            agent.provider._client = None  # force re-init
            console.print(f"[green]Provider set to:[/green] {arg} ({base_url})\n")
    elif command == "/history":
        convs = await db.list_conversations()
        if not convs:
            console.print("[dim]No conversations yet.[/dim]\n")
        else:
            for c in convs[:10]:
                console.print(f"  [dim]{c['id']}[/dim] {c['title'][:50]}")
        console.print()
    elif command == "/memories":
        memories = await db.list_memories(limit=20)
        if not memories:
            console.print("[dim]No memories yet. The agent learns as you chat.[/dim]\n")
        else:
            console.print(Panel("[bold]Agent Memories (Learning Store)[/bold]", border_style="magenta"))
            for m in memories:
                stars = "★" * int(m["confidence"] * 5) or "·"
                console.print(
                    f"  [magenta][{m['kind']}][/magenta] {m['content'][:80]} "
                    f"[dim]({stars}, used {m['times_used']}x)[/dim]"
                )
            console.print()
    elif command == "/memory":
        from agent.memory.memory_files import (
            read_memory_file, read_user_file, sync_db_to_files,
            MEMORY_FILE, USER_FILE,
        )
        if arg == "sync":
            # Sync DB memories to MEMORY.md file.
            all_mems = await db.list_memories(limit=500)
            sync_db_to_files(all_mems)
            console.print(f"[green]Synced {len(all_mems)} memories to {MEMORY_FILE}[/green]\n")
        elif arg == "show" or arg is None:
            # Show both memory files.
            mem_content = read_memory_file()
            usr_content = read_user_file()
            if mem_content:
                console.print(Panel(mem_content, title=f"[magenta]MEMORY.md[/magenta]", border_style="magenta"))
            else:
                console.print(f"[dim]{MEMORY_FILE} does not exist yet.[/dim]")
            if usr_content:
                console.print(Panel(usr_content, title=f"[cyan]USER.md[/cyan]", border_style="cyan"))
            else:
                console.print(f"[dim]{USER_FILE} does not exist yet.[/dim]")
            console.print()
        else:
            console.print("[yellow]Usage:[/yellow] /memory [show|sync]\n")
    elif command == "/sessions":
        parts = (arg or "").split(maxsplit=1)
        if not arg or parts[0] == "list":
            convs = await db.list_conversations(limit=20)
            if not convs:
                console.print("[dim]No sessions found.[/dim]\n")
            else:
                console.print(Panel(f"[bold]Sessions ({len(convs)})[/bold]", border_style="cyan"))
                for i, c in enumerate(convs, 1):
                    title = c["title"][:50]
                    cid = c["id"]
                    updated = c.get("updated_at", "?")[:19]
                    console.print(f"  [cyan]{i}.[/cyan] [bold]{title}[/bold] [dim]({cid})[/dim]")
                    console.print(f"     [dim]Updated: {updated}[/dim]")
                console.print(f"\n[dim]Use /sessions switch <id> to switch.[/dim]\n")
        elif parts[0] == "switch" and len(parts) > 1:
            target_id = parts[1].strip()
            msgs = await db.get_messages(target_id)
            if msgs:
                console.print(f"[green]Switched to session:[/green] {target_id} ({len(msgs)} messages)\n")
                console.print("[dim]Note: conversation history loaded for context.[/dim]\n")
            else:
                console.print(f"[red]Session not found:[/red] {target_id}\n")
        else:
            console.print("[yellow]Usage:[/yellow] /sessions [list|switch <id>]\n")
    elif command == "/export":
        if not arg:
            console.print("[yellow]Usage:[/yellow] /export <filename> or /export <session_id>\n")
        else:
            # Try to export the current conversation or by ID.
            target = arg.strip()
            msgs = await db.get_messages(target)
            if not msgs:
                console.print(f"[red]No session found with ID:[/red] {target}\n")
            else:
                lines = [f"# Nexa Agent — Session Export", f"Session: {target}", ""]
                for m in msgs:
                    role = m["role"]
                    content = m["content"]
                    if role == "user":
                        lines.append(f"## 🧑 User\n\n{content}\n")
                    elif role == "assistant":
                        lines.append(f"## ⚡ Nexa\n\n{content}\n")
                    elif role == "tool":
                        lines.append(f"<details><summary>🔧 {m.get('tool_name', 'tool')}</summary>\n\n```\n{content[:500]}\n```\n</details>\n")
                export_text = "\n".join(lines)
                # Write to workspace
                from nexa.config import NEXA_WORKSPACE
                export_path = NEXA_WORKSPACE / f"export_{target[:12]}.md"
                export_path.write_text(export_text, encoding="utf-8")
                console.print(f"[green]Exported to:[/green] {export_path}\n")
                console.print(f"[dim]{len(msgs)} messages exported.[/dim]\n")
    elif command == "/config":
        from nexa.config import NEXA_HOME, NEXA_WORKSPACE, NEXA_MODEL
        parts = (arg or "").split(maxsplit=2)
        if not arg or parts[0] == "show":
            console.print(Panel("[bold]Nexa Agent Configuration[/bold]", border_style="cyan"))
            console.print(f"  [cyan]NEXA_HOME[/cyan]:      {NEXA_HOME}")
            console.print(f"  [cyan]NEXA_WORKSPACE[/cyan]: {NEXA_WORKSPACE}")
            console.print(f"  [cyan]Provider[/cyan]:       {agent.provider.base_url}")
            console.print(f"  [cyan]Model[/cyan]:          {agent.provider.model}")
            console.print(f"  [cyan]API Key[/cyan]:        {'✓ set' if agent.provider.api_key else '✗ not set'}")
            console.print(f"  [cyan]Tools[/cyan]:          {len(agent.registry.list_names())} registered")
            console.print(f"  [cyan]Version[/cyan]:        {NEXA_VERSION}")
            console.print()
        elif parts[0] == "set" and len(parts) >= 3:
            key = parts[1]
            value = parts[2]
            if key == "model":
                agent.provider.model = value
                console.print(f"[green]Set model:[/green] {value}\n")
            elif key == "provider":
                base_url, model, api_key = resolve_provider(value)
                agent.provider.base_url = base_url
                agent.provider.model = model
                agent.provider.api_key = api_key
                agent.provider._client = None
                console.print(f"[green]Set provider:[/green] {value} ({base_url})\n")
            else:
                console.print(f"[red]Unknown config key:[/red] {key}. Available: model, provider\n")
        else:
            console.print("[yellow]Usage:[/yellow] /config [show|set <key> <value>]\n")
    elif command == "/doctor":
        console.print(Panel("[bold]Running self-health diagnostics...[/bold]", border_style="yellow"))
        health = SelfHealth(db)
        report = await health.run_full_check()
        console.print(report.summary())
        console.print()
    elif command == "/persona":
        # v2.0: show adaptive persona state.
        from agent.persona.adaptive_persona import AdaptivePersona
        p = AdaptivePersona()
        # In a full integration the persona would be a long-lived object
        # on the agent; here we display the neutral default for inspection.
        persona = p.persona()
        console.print(Panel("[bold]Adaptive Persona (v2.0)[/bold]", border_style="magenta"))
        console.print(f"  formality : [cyan]{persona.formality:.2f}[/cyan]")
        console.print(f"  verbosity : [cyan]{persona.verbosity:.2f}[/cyan]")
        console.print(f"  tone      : [cyan]{persona.tone}[/cyan]")
        console.print(f"  samples   : [cyan]{persona.samples}[/cyan]")
        console.print()
    elif command == "/knowledge":
        # v2.0: show cached learned facts.
        from agent.memory.knowledge_cache import KnowledgeCache
        cache = KnowledgeCache()
        facts = cache.list_all()
        if arg and arg.strip().lower() == "clear":
            n = cache.clear()
            console.print(f"[green]Cleared {n} cached fact(s).[/green]\n")
            return True
        if not facts:
            console.print("[yellow]No cached facts yet.[/yellow]\n")
            return True
        console.print(Panel(f"[bold]Cached Knowledge ({len(facts)})[/bold]", border_style="magenta"))
        for f in facts[:20]:
            console.print(f"  [cyan]{f.entity}[/cyan]: {f.summary[:80]}")
            console.print(f"    [dim]conf={f.confidence:.2f} hits={f.hits} src={f.source_title or 'N/A'}[/dim]")
        console.print()
    elif command == "/patterns":
        # v2.0: show recognized conversation patterns.
        from agent.understanding.pattern_recognizer import PatternRecognizer
        r = PatternRecognizer()
        report = r.report()
        console.print(Panel("[bold]Conversation Patterns (v2.0)[/bold]", border_style="magenta"))
        console.print(f"  avg message length : [cyan]{report.avg_msg_length}[/cyan] words")
        console.print(f"  terse ratio        : [cyan]{report.terse_ratio:.2f}[/cyan]")
        if report.top_topics:
            console.print("  top topics         :")
            for topic, count in report.top_topics:
                console.print(f"    - [green]{topic}[/green] ({count}x)")
        if report.tool_per_topic:
            console.print("  tool per topic     :")
            for topic, tool in report.tool_per_topic.items():
                console.print(f"    - {topic} → [green]{tool}[/green]")
        if report.suggestions:
            console.print("  [dim]suggestions:[/dim]")
            for s in report.suggestions:
                console.print(f"    - {s}")
        console.print()
    elif command == "/reflect":
        # v2.0: run a self-improvement reflection on the last turn.
        from agent.learning.self_improvement import SelfImprovementLoop
        loop = SelfImprovementLoop()
        # Without a stored last-turn, we just show the loop's stats.
        stats = loop.stats()
        console.print(Panel("[bold]Self-Improvement Reflection (v2.0)[/bold]", border_style="magenta"))
        console.print(f"  total improvements : [cyan]{stats['total']}[/cyan]")
        console.print(f"  by kind            : [cyan]{stats['by_kind']}[/cyan]")
        console.print(f"  top trigger        : [cyan]{stats.get('top_trigger') or 'N/A'}[/cyan]")
        console.print()
    else:
        console.print(f"[red]Unknown command:[/red] {command}. Type /help.\n")
    return True


async def run_turn(agent: NexaAgent, message: str, conv_id: str, history: list) -> None:
    """
    Run a single conversation turn and render streaming output.

    Args:
        agent:   The :class:`NexaAgent` instance.
        message: The user's message.
        conv_id: The conversation ID.
        history: The conversation history (mutated in place).
    """
    console.print()
    accumulated = ""
    try:
        async for event in agent.run_streaming(message, conv_id, history):
            if event["type"] == "thinking":
                console.print("[dim]Nexa is thinking...[/dim]", end="")
            elif event["type"] == "compressing":
                console.print(f"\n[yellow]⚠ {event.get('detail', 'compressing context')}[/yellow]")
            elif event["type"] == "token":
                accumulated += event["text"]
                console.print(event["text"], end="", style="white")
            elif event["type"] == "tool_result":
                tr = event["result"]
                status = "[green]✓[/green]" if tr["ok"] else "[red]✗[/red]"
                console.print(
                    Panel(
                        f"[dim]{tr['output'][:500]}[/dim]",
                        title=f"{status} [cyan]{event['name']}[/cyan] ({tr['duration_ms']}ms)",
                        border_style="cyan",
                        expand=False,
                    )
                )
            elif event["type"] == "memory":
                memories = event.get("memories", [])
                if memories:
                    console.print(
                        Panel(
                            "\n".join(
                                f"[magenta][{m['kind']}][/magenta] {m['content'][:80]}"
                                for m in memories
                            ),
                            title="[magenta]💾 Memory curated (agent is learning)[/magenta]",
                            border_style="magenta",
                            expand=False,
                        )
                    )
            elif event["type"] == "done":
                console.print("\n")
                console.print(Markdown(event["answer"]) if event["answer"] else "")
                console.print()
            elif event["type"] == "error":
                console.print(f"\n[red]Error:[/red] {event['message']}\n")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]\n")

    # Update history.
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": accumulated})


async def interactive_loop(agent: NexaAgent) -> None:
    """
    Run the interactive prompt loop.

    Args:
        agent: The :class:`NexaAgent` instance.
    """
    db = agent.db
    await db.init()
    conv = await db.create_conversation()
    history: list = []

    print_banner()

    while True:
        try:
            # Use input() for simplicity and maximum compatibility.
            # (prompt_toolkit is optional; we provide a rich rendering layer.)
            user_input = input("nexa > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            should_continue = await handle_slash_command(user_input, agent, db)
            if not should_continue:
                console.print("[dim]Goodbye![/dim]")
                break
            continue

        await run_turn(agent, user_input, conv["id"], history)


def main() -> None:
    """
    CLI entry point for ``python cli.py``.

    Examples::

        python cli.py
        python cli.py --provider ollama --model llama3.2
        python cli.py --provider openai --model gpt-4o
    """
    parser = argparse.ArgumentParser(
        description=f"{NEXA_NAME} — interactive terminal AI agent",
    )
    parser.add_argument("--provider", default=None, help="Provider name (ollama, openai, llamacpp, lmstudio, vllm)")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--base-url", default=None, help="Custom base URL")
    parser.add_argument("--api-key", default=None, help="API key override")
    args = parser.parse_args()

    agent = NexaAgent(
        provider_name=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )
    asyncio.run(interactive_loop(agent))


if __name__ == "__main__":
    main()
