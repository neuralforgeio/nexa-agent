"""
Nexa Agent — Terminal Tool
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
from typing import Any, Dict

from ..constants import NEXA_WORKSPACE
from .base import NexaTool, ToolParameter, ToolResult

BLOCKED_PATTERNS = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
]


class RunTerminalCommandTool(NexaTool):
    name = "run_terminal_command"
    description = (
        "Execute a shell command in the nexa workspace and return stdout/stderr. "
        "Output capped at 2000 chars. 15-second timeout."
    )
    parameters = {
        "command": ToolParameter("string", "The shell command to execute.", required=True),
    }

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(self.name, False, "command is required")

        lower = command.lower()
        for bad in BLOCKED_PATTERNS:
            if bad in lower:
                return ToolResult(self.name, False, f"blocked command pattern: '{bad}'")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(NEXA_WORKSPACE),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            out = stdout.decode("utf-8", errors="replace")[:2000]
            err = stderr.decode("utf-8", errors="replace")[:1000]
            parts = [f"exit code: {proc.returncode}"]
            if out:
                parts.append(f"stdout:\n{out}")
            if err:
                parts.append(f"stderr:\n{err}")
            if not out and not err:
                parts.append("(no output)")
            return ToolResult(self.name, True, "\n\n".join(parts))
        except asyncio.TimeoutError:
            return ToolResult(self.name, False, "command timed out (15s)")
        except Exception as e:
            return ToolResult(self.name, False, f"command failed: {e}")
