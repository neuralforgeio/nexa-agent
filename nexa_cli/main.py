"""
Nexa Agent — CLI Entry Point
============================

Non-interactive CLI subcommands for Nexa Agent.

Usage::
    python -m nexa_cli setup
    python -m nexa_cli model llama3.2
    python -m nexa_cli gateway start
    python -m nexa_cli gateway stop

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import sys
from typing import List, Optional

from nexa.constants import NEXA_NAME, NEXA_VERSION, ensure_nexa_home
from nexa.config import NEXA_HOME, NEXA_WORKSPACE


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point for nexa subcommands.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        prog="nexa",
        description=f"{NEXA_NAME} v{NEXA_VERSION} — CLI",
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

    # doctor
    subparsers.add_parser("doctor", help="Run self-health diagnostics")

    args = parser.parse_args(argv)

    if args.command == "setup":
        return _cmd_setup()
    elif args.command == "model":
        return _cmd_model(args.name)
    elif args.command == "gateway":
        return _cmd_gateway(args.action)
    elif args.command == "doctor":
        return _cmd_doctor()
    else:
        parser.print_help()
        return 0


def _cmd_setup() -> int:
    """
    Initialize ~/.nexa/ directory structure.

    Returns:
        0 on success.
    """
    ensure_nexa_home()
    print(f"[nexa] Home directory initialized: {NEXA_HOME}")
    print(f"[nexa] Workspace: {NEXA_WORKSPACE}")
    print(f"[nexa] Setup complete. Edit ~/.nexa/.env to configure your provider.")
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
        # Write to .env
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
        print(f"[nexa] Model set to: {name}")
    else:
        print(f"[nexa] Current model: {NEXA_MODEL}")
    return 0


def _cmd_gateway(action: str) -> int:
    """
    Manage the gateway server.

    Args:
        action: 'start', 'stop', or 'status'.

    Returns:
        0 on success.
    """
    import subprocess

    if action == "start":
        print("[nexa] Starting gateway server on port 8000...")
        proc = subprocess.Popen(
            ["python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        (NEXA_HOME / "gateway.pid").write_text(str(proc.pid))
        print(f"[nexa] Gateway started (PID: {proc.pid})")
        return 0
    elif action == "stop":
        pid_file = NEXA_HOME / "gateway.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text().strip())
            try:
                import os
                os.kill(pid, 9)
                print(f"[nexa] Gateway stopped (PID: {pid})")
            except ProcessLookupError:
                print("[nexa] Gateway process not found")
            pid_file.unlink()
        else:
            print("[nexa] Gateway not running")
        return 0
    elif action == "status":
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:8000/api/health", timeout=2)
            print("[nexa] Gateway: RUNNING (port 8000)")
            return 0
        except Exception:
            print("[nexa] Gateway: STOPPED")
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
        print(report.summary())
        return 0 if report.all_healthy else 1

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
