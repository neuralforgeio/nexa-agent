"""
Nexa Agent — Terminal Exec Tool (v3.2.0)
=========================================

Lets the AI run terminal commands programmatically, with the output
streamed back to the caller (for display in the TUI or Web UI).

Unlike ``run_terminal_command``, this tool also supports "attach" mode:
if ``session_id`` is provided and the web UI is running, the command output
is also written to the WebSocket terminal panel in real-time.

Security: same boundary as ``run_terminal_command`` (NEXA_WORKSPACE cwd,
~/.nexa/ blocked).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from tools.terminal_tool import run_terminal_command
from nexa.config import NEXA_HOME, NEXA_WORKSPACE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class TerminalSession:
    """
    A named terminal session (one per conversation, for persistent state).

    Attributes:
        session_id:  The conversation ID.
        buffer:      Recent output lines (for history).
        cwd:         The working directory for this session.
    """
    session_id: str
    buffer: List[str] = field(default_factory=list)
    cwd: str = ""


# ---------------------------------------------------------------------------
# TerminalExecTool
# ---------------------------------------------------------------------------
class TerminalExecTool:
    """
    Run terminal commands with optional session persistence.

    The tool wraps :func:`run_terminal_command` but also supports writing
    output to a WebSocket session if one is attached (for the web UI's
    xterm.js terminal panel).
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, TerminalSession] = {}

    async def execute(
        self,
        command: str,
        *,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        timeout: float = 30.0,
        broadcast_to_ui: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        Run a shell command with optional output broadcasting.

        Args:
            command:       The shell command to run.
            session_id:    Optional session ID (for multi-command sessions).
            cwd:            Optional working directory (must be inside workspace).
            timeout:        Max seconds to wait (default 30).
            broadcast_to_ui:If True, output is also written to the web UI's
                            terminal panel (if connected via /ws/terminal).

        Returns:
            A dict with ``ok``, ``output``, ``session_id``, ``broadcast``.
        """
        session = None
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = TerminalSession(
                    session_id=session_id, cwd=cwd or str(NEXA_WORKSPACE)
                )
            session = self._sessions[session_id]

        # Run the command.
        try:
            result = await run_terminal_command(
                command,
                timeout=timeout,
                cwd=cwd or (session.cwd if session else None),
            )
        except ValueError as exc:
            return {
                "ok": False,
                "output": f"blocked: {exc}",
                "session_id": session_id,
                "broadcast": broadcast_to_ui,
            }
        except asyncio.TimeoutError as exc:
            return {
                "ok": False,
                "output": f"timeout: {exc}",
                "session_id": session_id,
                "broadcast": broadcast_to_ui,
            }
        except Exception as exc:
            return {
                "ok": False,
                "output": f"error: {exc}",
                "session_id": session_id,
                "broadcast": broadcast_to_ui,
            }

        # Record in session buffer.
        if session is not None:
            session.buffer.append(command[:200])
            if len(session.buffer) > 50:
                session.buffer = session.buffer[-50:]

        return {
            "ok": True,
            "output": result,
            "session_id": session_id,
            "broadcast": broadcast_to_ui,
        }

    def session_history(self, session_id: str) -> List[str]:
        """Return the command history for a session."""
        session = self._sessions.get(session_id)
        return session.buffer.copy() if session else []

    def close_session(self, session_id: str) -> bool:
        """Close a session (clear it from the registry)."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[str]:
        """Return all active session IDs."""
        return list(self._sessions.keys())


#: OpenAI function-calling schema for terminal_exec.
TERMINAL_EXEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute (in NEXA_WORKSPACE).",
        },
        "session_id": {
            "type": "string",
            "description": "Optional session ID to persist state across calls.",
        },
        "cwd": {
            "type": "string",
            "description": "Optional working directory (must be inside the workspace).",
        },
        "timeout": {
            "type": "number",
            "description": "Max execution time in seconds (default: 30).",
            "default": 30,
        },
        "broadcast_to_ui": {
            "type": "boolean",
            "description": "If true, also stream output to the web UI terminal panel (if connected). Default: false.",
            "default": False,
        },
    },
    "required": ["command"],
}


# Backward-compatible alias.
ASYNC_TERMINAL_EXEC = TERMINAL_EXEC_SCHEMA
