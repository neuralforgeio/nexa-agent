"""
Nexa Agent — Planning Tools: Process & Port Intelligence (v4.1.0)
==================================================================

Two tools that let the agent inspect the host *without* any writes:

- :func:`list_ports`       — scan a set of common dev-server ports and report
  which are listening (plus the owning PID on Windows/POSIX).
- :func:`process_snapshot`  — a lightweight, regex-filtered snapshot of
  processes owned by the current user (no psutil dependency).

Both are read-only and defensive: any error is returned as a string, never
raised.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import re
import socket
import sys
from typing import Any, Dict, List, Optional


# Common dev-server ports that cover 95% of frameworks the sandbox previews.
_COMMON_PORTS: List[int] = [
    3000, 3001, 3002, 4000, 4173, 5000, 5173, 5174,
    5500, 7000, 8000, 8001, 8080, 8081, 8888, 9000,
]


async def _check_port(host: str, port: int, timeout: float = 0.4) -> bool:
    """Return whether a TCP connection to ``host:port`` succeeds."""
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _pid_for_port(port: int) -> Optional[int]:
    """
    Find the PID listening on ``port`` (Windows ``netstat`` or POSIX ``lsof``).

    Returns ``None`` when the owning process can't be determined (permissions
    or missing userland tool).
    """
    if sys.platform == "win32":
        try:
            proc = await asyncio.create_subprocess_exec(
                "netstat", "-ano",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except (OSError, asyncio.TimeoutError):
            return None
        needle = f":{port}"
        for line in stdout.decode("utf-8", "replace").splitlines():
            if "LISTENING" in line and needle in line:
                parts = line.split()
                try:
                    return int(parts[-1])
                except (ValueError, IndexError):
                    continue
        return None
    else:
        try:
            proc = await asyncio.create_subprocess_exec(
                "lsof", "-i", f"TCP:{port}", "-s", "TCP:LISTEN", "-t",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            out = stdout.decode("utf-8", "replace").strip()
            return int(out) if out.isdigit() else None
        except (OSError, asyncio.TimeoutError, ValueError):
            return None


async def list_ports(host: str = "127.0.0.1", ports: Optional[List[int]] = None) -> str:
    """
    Scan dev-server ports and report which are accepting connections.

    Args:
        host:  The host to probe (default ``127.0.0.1``).
        ports: An explicit list of ports; defaults to a curated set of
               common dev ports (3000, 5173, 8000, 8080, …).

    Returns:
        A Markdown table of listening ports and (when resolvable) the
        owning PID / process label.
    """
    ports = ports or _COMMON_PORTS
    results = await asyncio.gather(*(_check_port(host, p) for p in ports))
    listening = [p for p, ok in zip(ports, results) if ok]

    if not listening:
        return (
            f"No dev servers listening on `{host}` "
            f"(scanned {len(ports)} ports)."
        )

    pid_rows: List[str] = []
    for p in listening:
        pid = await _pid_for_port(p)
        pid_rows.append(f"| {p} | {'🟢 listening' if True else ''} | {pid or '—'} |")

    header = (
        f"**{len(listening)} port(s) listening on {host}:**\n\n"
        "| Port | Status | PID |\n|---|---|---|"
    )
    return header + "\n" + "\n".join(pid_rows)


LIST_PORTS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "host": {"type": "string", "default": "127.0.0.1"},
        "ports": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Explicit ports; defaults to the curated dev port set.",
        },
    },
    "required": [],
}


# ---------------------------------------------------------------------------
# process_snapshot
# ---------------------------------------------------------------------------
async def process_snapshot(name_filter: str = "", limit: int = 25) -> str:
    """
    Snapshot user processes, optionally filtered by a regex over the name.

    Uses ``tasklist`` on Windows and ``ps`` on POSIX — no third-party
    dependency, read-only, defensive (never raises).

    Args:
        name_filter: Regex (case-insensitive) over the process name.
        limit:       Maximum rows to return (default 25, max 100).

    Returns:
        A Markdown table of matching processes.
    """
    limit = max(1, min(limit, 100))
    try:
        pattern = re.compile(name_filter or ".", re.IGNORECASE)
    except re.error as exc:
        return f"**Invalid regex:** {exc}"

    rows: List[str] = []
    if sys.platform == "win32":
        # tasklist /FO CSV gives us: "Name","PID","Session","Mem"
        proc = await asyncio.create_subprocess_exec(
            "tasklist", "/FO", "CSV",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        lines = stdout.decode("utf-8", "replace").splitlines()[1:]  # skip header
        for line in lines:
            if len(rows) >= limit:
                break
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) < 2:
                continue
            name = parts[0].strip('"')
            pid = parts[1]
            if pattern.search(name):
                rows.append((name, pid, parts[-1] if len(parts) >= 5 else ""))
    else:
        proc = await asyncio.create_subprocess_exec(
            "ps", "-eo", "pid,comm",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        lines = stdout.decode("utf-8", "replace").splitlines()[1:]
        for line in lines:
            if len(rows) >= limit:
                break
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            pid, name = parts[0], parts[1]
            if pattern.search(name):
                rows.append((name, pid, ""))

    if not rows:
        return f"No processes matching `{name_filter or '.'}` found."

    table = "| Process | PID | Info |\n|---|---|---|\n"
    table += "\n".join(f"| `{n}` | {p} | {i} |" for n, p, i in rows)
    return f"**{len(rows)} process(es) matching `{name_filter or '.'}`:**\n\n{table}"


PROCESS_SNAPSHOT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name_filter": {"type": "string", "description": "Regex over process name.", "default": ""},
        "limit": {"type": "integer", "default": 25},
    },
    "required": [],
}
