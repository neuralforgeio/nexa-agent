"""
Nexa Agent — Terminal & Utility Tools
=====================================

This module provides ``run_terminal_command`` (shell execution sandboxed
to the workspace, with a timeout and output cap) and ``generate_uuid``
(a simple UUID v4 generator).

Dangerous command patterns (e.g. ``rm -rf /``, ``mkfs``, ``shutdown``)
are blocked to prevent accidental damage.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import uuid
from typing import Any

from config import NEXA_WORKSPACE

#: Substrings that cause a command to be rejected outright.
BLOCKED_PATTERNS: list[str] = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
]


async def run_terminal_command(command: str, **_: Any) -> str:
    """
    Execute a shell command in the nexa workspace.

    The command runs via ``asyncio.create_subprocess_shell`` with the
    working directory set to ``NEXA_WORKSPACE``. stdout and stderr are
    captured; stdout is capped at 2000 chars and stderr at 1000 chars.
    A 15-second timeout is enforced.

    Args:
        command: The shell command to execute.

    Returns:
        A formatted string containing the exit code, stdout, and stderr.

    Raises:
        ValueError: If the command matches a blocked pattern.
        asyncio.TimeoutError: If the command does not finish in 15 seconds.
    """
    lower = command.lower()
    for bad in BLOCKED_PATTERNS:
        if bad in lower:
            raise ValueError(f"blocked command pattern: '{bad}'")

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(NEXA_WORKSPACE),
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=15.0
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise asyncio.TimeoutError("command timed out (15s)")

    out = stdout_bytes.decode("utf-8", errors="replace")[:2000]
    err = stderr_bytes.decode("utf-8", errors="replace")[:1000]
    parts: list[str] = [f"exit code: {proc.returncode}"]
    if out:
        parts.append(f"stdout:\n{out}")
    if err:
        parts.append(f"stderr:\n{err}")
    if not out and not err:
        parts.append("(no output)")
    return "\n\n".join(parts)


async def generate_uuid(**_: Any) -> str:
    """
    Generate a random UUID v4 string.

    Returns:
        A 36-character UUID string (e.g. ``"550e8400-e29b-41d4-a716-446655440000"``).
    """
    return str(uuid.uuid4())
