"""
OpenForge — CLI Entry Point (Polished v2.1.0)
===============================================

Non-interactive CLI subcommands for OpenForge.

Hardening (v2.1.0):
    - Uses :data:`sys.executable` for spawning subprocesses (cross-platform,
      not hardcoded ``python3``).
    - ``gateway stop`` sends ``SIGTERM`` first (graceful) before SIGKILL.
    - ``gateway start`` accepts a ``--port`` flag (default 8000).
    - ``--help`` output rendered with a :class:`rich.table.Table` for
      readability.

Usage::
    python -m openforge_cli setup
    python -m openforge_cli model llama3.2
    python -m openforge_cli gateway start --port 9000
    python -m openforge_cli gateway stop
    python -m openforge_cli doctor

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import os
import signal
import subprocess
import sys
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from openforge.constants import (
    FORGE_NAME,
    FORGE_VERSION,
    ensure_forge_home
)
from openforge.config import FORGE_HOME, FORGE_WORKSPACE

console = Console()

#: Default gateway port.
DEFAULT_GATEWAY_PORT: int = 8000


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point for openforge subcommands.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success, 1 for error).

    Example:
        >>> main(["setup"])  # doctest: +SKIP
        0
    """
    parser = argparse.ArgumentParser(
        prog="openforge",
        description=f"{FORGE_NAME} v{FORGE_VERSION} — CLI",
        add_help=True,
    )
    # v4.2.3: top-level --version flag (parses and exits before subcommands).
    parser.add_argument(
        "-V", "--version",
        action="store_true",
        help="Print the current openforge version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    subparsers.add_parser("setup", help="Initialize ~/.openforge/ and configure provider")

    # model
    model_parser = subparsers.add_parser("model", help="Show or set the current model")
    model_parser.add_argument("name", nargs="?", help="Model name to set")

    # gateway
    gateway_parser = subparsers.add_parser("gateway", help="Manage the gateway server")
    gateway_parser.add_argument(
        "action", choices=["start", "stop", "status"], help="Gateway action"
    )
    gateway_parser.add_argument(
        "--port", type=int, default=DEFAULT_GATEWAY_PORT,
        help=f"Port for the gateway server (default: {DEFAULT_GATEWAY_PORT})",
    )

    # provider (v4.1.0): interactive add/use/list/remove/test
    provider_parser = subparsers.add_parser(
        "provider", help="Manage LLM providers (add/use/list/remove/test)"
    )
    provider_parser.add_argument(
        "action", choices=["add", "use", "list", "remove", "test"],
        help="Provider action",
    )
    provider_parser.add_argument(
        "name", nargs="?", default=None,
        help="Provider name (for use/remove/test). For 'add', omit and enter interactively.",
    )
    provider_parser.add_argument(
        "--base-url", default=None,
        help="Base URL for 'add' (skip interactive prompt).",
    )
    provider_parser.add_argument(
        "--api-key", default=None,
        help="API key for 'add' (skip interactive prompt).",
    )
    provider_parser.add_argument(
        "--model", default=None,
        help="Default model ID for 'add' (skip interactive prompt).",
    )

    # doctor
    subparsers.add_parser("doctor", help="Run self-health diagnostics")

    # plugin (S-09): install a plugin from a git URL
    plugin_parser = subparsers.add_parser("plugin", help="Install a community plugin")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command")
    install_p = plugin_sub.add_parser("install", help="Install a plugin from a git URL")
    install_p.add_argument("url", help="Git URL of the plugin repository")

    args = parser.parse_args(argv)

    # v4.2.3: --version short-circuit (handled BEFORE subcommand dispatch).
    if getattr(args, "version", False):
        print(f"{FORGE_NAME} v{FORGE_VERSION}")
        return 0

    if args.command == "setup":
        return _cmd_setup()
    elif args.command == "model":
        return _cmd_model(args.name)
    elif args.command == "gateway":
        return _cmd_gateway(args.action, args.port)
    elif args.command == "provider":
        return _cmd_provider(
            args.action,
            name=args.name,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
        )
    elif args.command == "doctor":
        return _cmd_doctor()
    elif args.command == "plugin":
        if getattr(args, "plugin_command", None) == "install":
            return _cmd_plugin_install(args.url)
        print("Usage: openforge plugin install <git-url>")
        return 1
    else:
        _print_rich_help()
        return 0


def _cmd_plugin_install(url: str) -> int:
    """Clone a plugin repo into ~/.openforge/plugins/<name>/ and register it. (S-09)"""
    import re
    from pathlib import Path

    if not re.match(r"^https?://", url):
        console.print(f"[red]Invalid URL: {url}[/red]")
        return 1
    name = url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
    plugin_dir = Path.home() / ".openforge" / "plugins" / name
    plugin_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["git", "clone", url, str(plugin_dir)], check=True, capture_output=True, text=True)
        console.print(f"[green]Plugin installed: {plugin_dir}[/green]")
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Install failed: {e.stderr}[/red]")
        return 1


def _print_rich_help() -> None:
    """Print a rich-rendered help table listing all subcommands."""
    table = Table(title=f"{FORGE_NAME} v{FORGE_VERSION} — Subcommands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Example", style="dim")

    rows = [
        ("setup", "Initialize ~/.openforge/ and configure provider", "openforge setup"),
        ("model", "Show or set the current model", "openforge model llama3.2"),
        ("gateway start", "Start the gateway server", "openforge gateway start --port 8000"),
        ("gateway stop", "Stop the gateway server (graceful SIGTERM)", "openforge gateway stop"),
        ("gateway status", "Check if the gateway server is running", "openforge gateway status"),
        ("provider list", "List all LLM providers (v4.1.0)", "openforge provider list"),
        ("provider add", "Interactively add a custom provider (v4.1.0)", "openforge provider add tokenrouter"),
        ("provider use", "Switch the active provider (v4.1.0)", "openforge provider use tokenrouter"),
        ("provider remove", "Remove a custom provider (v4.1.0)", "openforge provider remove tokenrouter"),
        ("provider test", "Health-check a provider (v4.1.0)", "openforge provider test openai"),
        ("doctor", "Run self-health diagnostics", "openforge doctor"),
    ]
    for cmd, desc, example in rows:
        table.add_row(cmd, desc, example)

    console.print(Panel(table, border_style="cyan", title="[cyan]OpenForge CLI[/cyan]"))
    console.print(
        "\n[dim]Type 'openforge <command> --help' for command-specific options.[/dim]"
    )
    console.print(
        "[dim]For the interactive chat REPL, use 'openforge-chat'.[/dim]\n"
    )


def _cmd_setup() -> int:
    """
    Initialize ~/.openforge/ directory structure.

    Returns:
        0 on success.
    """
    ensure_forge_home()
    console.print(Panel(
        f"[green]Home directory initialized:[/green] {FORGE_HOME}\n"
        f"[green]Workspace:[/green] {FORGE_WORKSPACE}\n"
        f"Setup complete. Edit ~/.openforge/.env to configure your provider.",
        border_style="green",
        title="[green]OpenForge Setup[/green]",
    ))
    return 0


def _cmd_model(name: Optional[str]) -> int:
    """
    Show or set the current model.

    Args:
        name: Model name to set, or None to show current.

    Returns:
        0 on success.
    """
    from openforge.config import NEXA_MODEL

    if name:
        env_path = FORGE_HOME / ".env"
        if env_path.exists():
            content = env_path.read_text()
            if "NEXA_MODEL=" in content:
                import re
                content = re.sub(r"NEXA_MODEL=.*", f"NEXA_MODEL={name}", content)
            else:
                content += f"\nNEXA_MODEL={name}\n"
            env_path.write_text(content)
        else:
            env_path.write_text(f"NEXA_MODEL={name}\n")
        console.print(f"[green]Model set to:[/green] {name}")
    else:
        console.print(f"[cyan]Current model:[/cyan] {NEXA_MODEL}")
    return 0


def _cmd_gateway(action: str, port: int = DEFAULT_GATEWAY_PORT) -> int:
    """
    Manage the gateway server.

    Args:
        action: 'start', 'stop', or 'status'.
        port:    Port for the server (default 8000).

    Returns:
        0 on success.
    """
    if action == "start":
        console.print(f"[cyan]Starting gateway server on port {port}...[/cyan]")
        # v2.1.0: use sys.executable (cross-platform), not hardcoded "python3".
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "server:app",
                "--host", "0.0.0.0", "--port", str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        (FORGE_HOME / "gateway.pid").write_text(str(proc.pid))
        console.print(f"[green]Gateway started[/green] (PID: {proc.pid}, port: {port})")
        return 0
    elif action == "stop":
        pid_file = FORGE_HOME / "gateway.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            try:
                # v2.1.0: SIGTERM first (graceful), then SIGKILL as fallback.
                os.kill(pid, signal.SIGTERM)
                # Give it 3 seconds to shut down gracefully.
                import time
                for _ in range(30):
                    try:
                        os.kill(pid, 0)  # Check if still alive.
                        time.sleep(0.1)
                    except ProcessLookupError:
                        break
                else:
                    # Still alive after 3s — force kill.
                    # Windows doesn't have signal.SIGKILL; use the raw value 9.
                    try:
                        if sys.platform == "win32":
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                        else:
                            os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                console.print(f"[green]Gateway stopped[/green] (PID: {pid})")
            except ProcessLookupError:
                console.print("[yellow]Gateway process not found[/yellow]")
            pid_file.unlink()
        else:
            console.print("[yellow]Gateway not running[/yellow]")
        return 0
    elif action == "status":
        import urllib.request
        try:
            urllib.request.urlopen(f"http://localhost:{port}/api/health", timeout=2)
            console.print(f"[green]Gateway: RUNNING[/green] (port {port})")
            return 0
        except Exception:
            console.print("[red]Gateway: STOPPED[/red]")
            return 1
    return 0


def _cmd_provider(
    action: str,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> int:
    """
    Manage LLM providers (v4.1.0): add / use / list / remove / test.

    Args:
        action:  One of 'add', 'use', 'list', 'remove', 'test'.
        name:    Provider name (for use/remove/test). For 'add', prompts if None.
        base_url: Base URL override for 'add' (skip prompt).
        api_key:  API key override for 'add' (skip prompt).
        model:    Default model override for 'add' (skip prompt).

    Returns:
        0 on success, 1 on error.

    Example:
        >>> _cmd_provider("add", name="tokenrouter")  # doctest: +SKIP
        ? API key (tr_...): ********
        ? Model ID [auto:balance]:
        ✓ Saved tokenrouter to ~/.openforge/secrets/providers.json
    """
    import asyncio
    from openforge.provider_registry import (
        ProviderRegistry,
        StoredProviderConfig,
    )
    from providers.catalog import PROVIDER_CATALOG

    reg = ProviderRegistry()

    if action == "list":
        all_providers = reg.list_all()
        table = Table(
            title="OpenForge — LLM Providers",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Base URL", style="white")
        table.add_column("Model", style="green")
        table.add_column("API Key", style="dim")
        active = reg.get_active()
        for p in all_providers:
            marker = "→" if active and active.name == p.name else " "
            key_display = p.api_key or "(env)"
            table.add_row(
                f"{marker} {p.name}",
                p.base_url or "(set NEXA_BASE_URL)",
                p.model or "(default)",
                key_display,
            )
        console.print(Panel(table, border_style="cyan", title="[cyan]Providers[/cyan]"))
        return 0

    if action == "add":
        # Determine the provider name.
        if name is None:
            console.print("[cyan]Available catalog providers:[/cyan]")
            for n in PROVIDER_CATALOG:
                console.print(f"  - {n}")
            console.print("  - <custom name> (for any OpenAI-compatible endpoint)")
            name = input("Provider name: ").strip()
            if not name:
                console.print("[red]Provider name is required.[/red]")
                return 1
        # Default base_url + model from catalog if known.
        cat = PROVIDER_CATALOG.get(name)
        default_base = base_url or (cat.base_url if cat else "")
        default_model = model or (cat.default_model if cat else "gpt-4o")
        # Prompt for missing values.
        if base_url is None:
            prompt_url = f"Base URL [{default_base}]: " if default_base else "Base URL: "
            entered = input(prompt_url).strip()
            if entered:
                default_base = entered
            elif not default_base:
                console.print("[red]Base URL is required.[/red]")
                return 1
        if api_key is None:
            try:
                import getpass
                api_key = getpass.getpass("API key (input hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[red]Aborted.[/red]")
                return 1
            if not api_key and cat and cat.name not in ("ollama", "llamacpp", "lmstudio", "vllm"):
                console.print("[yellow]Warning: empty API key for non-local provider.[/yellow]")
                api_key = api_key or "dummy"
        if model is None:
            entered = input(f"Model ID [{default_model}]: ").strip()
            if entered:
                default_model = entered
        # Save.
        cfg = StoredProviderConfig(
            name=name,
            base_url=default_base,
            api_key=api_key,
            model=default_model,
        )
        reg.add(name, cfg)
        console.print(f"[green]✓ Saved[/green] {name} to ~/.openforge/secrets/providers.json")
        console.print(f"  base_url: [cyan]{default_base}[/cyan]")
        console.print(f"  model:    [green]{default_model}[/green]")
        console.print(f"  api_key:  [dim]{cfg.masked_api_key()}[/dim]")
        console.print(f"\n[dim]Activate with:[/dim] openforge provider use {name}")
        return 0

    if action == "use":
        if not name:
            console.print("[red]Usage: openforge provider use <name>[/red]")
            return 1
        if reg.set_active(name):
            console.print(f"[green]✓ Switched to[/green] {name}")
            cfg = reg.get_active()
            if cfg:
                console.print(f"  base_url: [cyan]{cfg.base_url}[/cyan]")
                console.print(f"  model:    [green]{cfg.model}[/green]")
            return 0
        console.print(f"[red]Unknown provider:[/red] {name}")
        console.print("[dim]Available: openforge provider list[/dim]")
        return 1

    if action == "remove":
        if not name:
            console.print("[red]Usage: openforge provider remove <name>[/red]")
            return 1
        if reg.remove(name):
            console.print(f"[green]✓ Removed[/green] {name}")
            return 0
        console.print(f"[red]No such provider:[/red] {name}")
        return 1

    if action == "test":
        if not name:
            console.print("[red]Usage: openforge provider test <name>[/red]")
            return 1
        console.print(f"[cyan]Probing[/cyan] {name}...")
        try:
            healthy = asyncio.run(reg.test(name))
        except Exception as exc:
            console.print(f"[red]✗ Health check failed:[/red] {exc}")
            return 1
        if healthy:
            console.print(f"[green]✓ {name} is healthy (responded 200).[/green]")
            return 0
        console.print(f"[red]✗ {name} is unreachable or returned an error.[/red]")
        return 1

    return 0


def _cmd_doctor() -> int:
    """
    Run self-health diagnostics.

    Returns:
        0 if healthy, 1 if issues found.
    """
    import asyncio
    from openforge.state import ConversationDB
    from agent.core.self_health import SelfHealth

    async def run():
        db = ConversationDB()
        await db.init()
        health = SelfHealth(db)
        report = await health.run_full_check()
        console.print(Panel(report.summary(), border_style="yellow", title="[yellow]OpenForge Health Report[/yellow]"))
        return 0 if report.all_healthy else 1

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
