"""
Nexa Agent — CLI Entry Point (Polished v2.1.0)
==============================================

Non-interactive CLI subcommands for Nexa Agent.

Hardening (v2.1.0):
    - Uses :data:`sys.executable` for spawning subprocesses (cross-platform,
      not hardcoded ``python3``).
    - ``gateway stop`` sends ``SIGTERM`` first (graceful) before SIGKILL.
    - ``gateway start`` accepts a ``--port`` flag (default 8000).
    - ``--help`` output rendered with a :class:`rich.table.Table` for
      readability.

Usage::
    python -m nexa_cli setup
    python -m nexa_cli model llama3.2
    python -m nexa_cli gateway start --port 9000
    python -m nexa_cli gateway stop
    python -m nexa_cli doctor

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

from nexa.constants import NEXA_NAME, NEXA_VERSION, ensure_nexa_home
from nexa.config import NEXA_HOME, NEXA_WORKSPACE

console = Console()

#: Default gateway port.
DEFAULT_GATEWAY_PORT: int = 8000


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point for nexa subcommands.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success, 1 for error).

    Example:
        >>> main(["setup"])  # doctest: +SKIP
        0
    """
    parser = argparse.ArgumentParser(
        prog="nexa",
        description=f"{NEXA_NAME} v{NEXA_VERSION} — CLI",
        add_help=True,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    subparsers.add_parser("setup", help="Initialize ~/.nexa/ and configure provider")

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

    # doctor
    subparsers.add_parser("doctor", help="Run self-health diagnostics")

    args = parser.parse_args(argv)

    if args.command == "setup":
        return _cmd_setup()
    elif args.command == "model":
        return _cmd_model(args.name)
    elif args.command == "gateway":
        return _cmd_gateway(args.action, args.port)
    elif args.command == "doctor":
        return _cmd_doctor()
    else:
        _print_rich_help()
        return 0


def _print_rich_help() -> None:
    """Print a rich-rendered help table listing all subcommands."""
    table = Table(title=f"{NEXA_NAME} v{NEXA_VERSION} — Subcommands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Example", style="dim")

    rows = [
        ("setup", "Initialize ~/.nexa/ and configure provider", "nexa setup"),
        ("model", "Show or set the current model", "nexa model llama3.2"),
        ("gateway start", "Start the gateway server", "nexa gateway start --port 8000"),
        ("gateway stop", "Stop the gateway server (graceful SIGTERM)", "nexa gateway stop"),
        ("gateway status", "Check if the gateway server is running", "nexa gateway status"),
        ("doctor", "Run self-health diagnostics", "nexa doctor"),
    ]
    for cmd, desc, example in rows:
        table.add_row(cmd, desc, example)

    console.print(Panel(table, border_style="cyan", title="[cyan]Nexa Agent CLI[/cyan]"))
    console.print(
        "\n[dim]Type 'nexa <command> --help' for command-specific options.[/dim]"
    )
    console.print(
        "[dim]For the interactive chat REPL, use 'nexa-chat'.[/dim]\n"
    )


def _cmd_setup() -> int:
    """
    Initialize ~/.nexa/ directory structure.

    Returns:
        0 on success.
    """
    ensure_nexa_home()
    console.print(Panel(
        f"[green]Home directory initialized:[/green] {NEXA_HOME}\n"
        f"[green]Workspace:[/green] {NEXA_WORKSPACE}\n"
        f"Setup complete. Edit ~/.nexa/.env to configure your provider.",
        border_style="green",
        title="[green]Nexa Setup[/green]",
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
    from nexa.config import NEXA_MODEL

    if name:
        env_path = NEXA_HOME / ".env"
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
        (NEXA_HOME / "gateway.pid").write_text(str(proc.pid))
        console.print(f"[green]Gateway started[/green] (PID: {proc.pid}, port: {port})")
        return 0
    elif action == "stop":
        pid_file = NEXA_HOME / "gateway.pid"
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


def _cmd_doctor() -> int:
    """
    Run self-health diagnostics.

    Returns:
        0 if healthy, 1 if issues found.
    """
    import asyncio
    from nexa.state import ConversationDB
    from agent.self_health import SelfHealth

    async def run():
        db = ConversationDB()
        await db.init()
        health = SelfHealth(db)
        report = await health.run_full_check()
        console.print(Panel(report.summary(), border_style="yellow", title="[yellow]Nexa Health Report[/yellow]"))
        return 0 if report.all_healthy else 1

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
