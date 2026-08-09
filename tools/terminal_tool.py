"""
OpenForge — Terminal & Utility Tools
=====================================

This module provides:

    - :func:`run_terminal_command` — Execute a shell command with configurable
      timeout, output truncation, environment variables, and working directory.
      Dangerous patterns are blocked. Background process management is supported
      via the ``background`` parameter.
    - :func:`generate_uuid` — Generate a random UUID v4 string.
    - :func:`list_background_processes` — List currently running background
      processes spawned by the agent.
    - :func:`kill_background_process` — Terminate a background process by ID.

Design Philosophy:
    - **Non-blocking**: All execution is async via ``asyncio``.
    - **Sandboxed**: Commands run in ``FORGE_WORKSPACE`` by default.
    - **Safe**: Dangerous patterns are blocked. Output is capped to prevent
      memory exhaustion.
    - **Observable**: Background processes are tracked and can be listed/killed.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openforge.config import FORGE_WORKSPACE

#: Substrings that cause a command to be rejected outright.
# Includes both Unix and Windows dangerous patterns (case-insensitive match).
BLOCKED_PATTERNS: list[str] = [
    # Unix destructive patterns.
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    # Windows destructive patterns (PowerShell + cmd).
    "del /s",
    "del /f",
    "format ",
    "rmdir /s",
    "rd /s",
    "remove-item -recurse",
    "remove-item -force",
    "remove-item -r",
    "shutdown /s",
    "shutdown /r",
    "diskpart",
    "reg delete",
]

#: Maximum stdout output length (characters).
MAX_STDOUT: int = 2000

#: Maximum stderr output length (characters).
MAX_STDERR: int = 1000

#: Default command timeout in seconds.
DEFAULT_TIMEOUT: float = 15.0

#: Maximum allowed timeout in seconds (prevents excessively long commands).
MAX_TIMEOUT: float = 60.0

#: After this many completed background processes accumulate, prune runs.
PRUNE_THRESHOLD: int = 10


@dataclass
class BackgroundProcess:
    """
    Tracks a background process spawned by the agent.

    Attributes:
        pid:        The unique process ID (Nexa-assigned, not OS PID).
        command:    The shell command that was executed.
        process:    The underlying ``asyncio.subprocess.Process`` object.
        started_at: The Unix timestamp when the process was started.
        status:     The current status: 'running', 'completed', 'killed'.
    """

    pid: str
    command: str
    process: asyncio.subprocess.Process
    started_at: float
    status: str = "running"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize this process to a dict for display.

        Returns:
            A dict with pid, command, started_at, and status.
        """
        import time
        return {
            "pid": self.pid,
            "command": self.command[:80],
            "started_at": self.started_at,
            "elapsed": round(time.time() - self.started_at, 1),
            "status": self.status,
        }


#: Registry of background processes, keyed by Nexa-assigned PID.
_background_processes: Dict[str, BackgroundProcess] = {}


async def run_terminal_command(
    command: str,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    background: bool = False,
    **_: Any,
) -> str:
    """
    Execute a shell command in the nexa workspace.

    The command runs via ``asyncio.create_subprocess_shell`` with full
    async I/O. stdout and stderr are captured and truncated to prevent
    memory exhaustion. A configurable timeout is enforced.

    Args:
        command:    The shell command to execute.
        timeout:    Maximum execution time in seconds (default: 15, max: 60).
        cwd:        Working directory override (default: FORGE_WORKSPACE).
        env:        Additional environment variables to merge with os.environ.
        background: If True, the process runs in the background and its
                    PID is returned immediately. Use ``list_background_processes``
                    to check status.

    Returns:
        For foreground: A formatted string with exit code, stdout, and stderr.
        For background: A message with the assigned process ID.

    Raises:
        ValueError: If the command is empty, matches a blocked pattern,
                    or the timeout exceeds MAX_TIMEOUT.
        asyncio.TimeoutError: If the command does not finish in time.
    """
    # Reject empty or whitespace-only commands.
    if not command or not command.strip():
        raise ValueError("command is empty or whitespace-only")

    # v3.0.0: Block commands that try to access FORGE_HOME (security boundary).
    # This prevents the LLM from exfiltrating API keys / secrets / memory
    # stored in ~/.openforge/ via shell commands like `cat ~/.openforge/.env`.
    if is_protected_path_reference(command):
        raise ValueError(
            "command accesses protected FORGE_HOME path (~/.openforge/). "
            "Terminal commands cannot read or write files inside FORGE_HOME "
            "to prevent API key / secrets exfiltration."
        )

    # Check against blocked patterns.
    lower = command.lower()
    for bad in BLOCKED_PATTERNS:
        if bad in lower:
            # Raise so the registry sets ToolResult(ok=False)
            raise ValueError(f"blocked command pattern: '{bad}' — terminal rejects")

    # Validate and clamp timeout.
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    if timeout > MAX_TIMEOUT:
        raise ValueError(f"timeout {timeout}s exceeds maximum {MAX_TIMEOUT}s")

    # Build environment.
    # v4.1.0 security: whitelist only non-secret keys so commands cannot
    # leak OPENAI_API_KEY / DATABRICKS_TOKEN / *_API_KEY / *_TOKEN into a
    # subprocess that might pipe them to a remote server.
    _ALLOWED_ENV = {
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SHELL",
        "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP", "PROMPT", "PS1", "PS2",
        # Platform essentials (Windows needs these to find cmd.exe etc.)
        "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "OS",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROGRAMFILES",
        "PROGRAMFILES(X86)", "PROGRAMDATA", "APPDATA", "LOCALAPPDATA",
        # Toolchain paths
        "PYTHONPATH", "VIRTUAL_ENV",
    }
    full_env: Dict[str, str] = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in _ALLOWED_ENV
        and not k.upper().endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
    }
    if env:
        for k, v in env.items():
            if k.upper().endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
                continue  # never let a tool-specified secret through either
            if k.upper() in ("HOME", "FORGE_HOME", "FORGE_WORKSPACE"):
                continue  # don't let caller redirect HOME back to ~/
            full_env[k] = v

    # Resolve working directory (project-scoped boundary).
    work_dir = _validate_cwd(cwd)

    # v4.1.2 security: override HOME/FORGE_HOME/FORGE_WORKSPACE so any
    # ``chr(126)+chr(47)+chr(46)+chr(110)...``-style obfuscated path (or any
    # ``os.path.expanduser('~/.openforge/...')`` call inside a spawned Python)
    # resolves to the workspace, NOT the real user home. Without this the
    # entire chr()-based exfiltration family works because the regex block
    # matches nothing on the command string.
    full_env["HOME"] = str(work_dir)
    full_env["FORGE_HOME"] = str(work_dir)
    full_env["FORGE_WORKSPACE"] = str(work_dir)

    # Spawn the process with a new process group (so timeout can kill the tree).
    popen_kwargs: Dict[str, Any] = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "cwd": str(work_dir),
        "env": full_env,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    proc = await asyncio.create_subprocess_shell(command, **popen_kwargs)

    # Background mode: register and return immediately.
    if background:
        import time
        pid = f"bg-{uuid.uuid4().hex[:8]}"
        bg_proc = BackgroundProcess(
            pid=pid,
            command=command,
            process=proc,
            started_at=time.time(),
        )
        _background_processes[pid] = bg_proc
        # Schedule a background task to update status when complete.
        asyncio.create_task(_track_background_process(bg_proc))
        return f"Background process started. PID: {pid}\nCommand: {command[:100]}"

    # Foreground mode: wait for completion with timeout.
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        # Robust kill: take down the whole process tree.
        await _kill_process_tree(proc)
        try:
            await proc.wait()
        except Exception:
            pass
        raise asyncio.TimeoutError(f"command timed out ({timeout}s)")

    # Decode and truncate output.
    out = stdout_bytes.decode("utf-8", errors="replace")[:MAX_STDOUT]
    err = stderr_bytes.decode("utf-8", errors="replace")[:MAX_STDERR]

    # Build the result string.
    parts: List[str] = [f"exit code: {proc.returncode}"]
    if out:
        truncated = "…[truncated]" if len(stdout_bytes) > MAX_STDOUT else ""
        parts.append(f"stdout:{truncated}\n{out}")
    if err:
        truncated = "…[truncated]" if len(stderr_bytes) > MAX_STDERR else ""
        parts.append(f"stderr:{truncated}\n{err}")
    if not out and not err:
        parts.append("(no output)")
    return "\n\n".join(parts)


async def _track_background_process(bg_proc: BackgroundProcess) -> None:
    """
    Wait for a background process to complete and update its status.

    Args:
        bg_proc: The :class:`BackgroundProcess` to track.
    """
    try:
        await bg_proc.process.wait()
        bg_proc.status = "completed"
    except asyncio.CancelledError:
        bg_proc.status = "killed"
    except Exception:
        bg_proc.status = "error"


async def list_background_processes(**_: Any) -> str:
    """
    List all background processes spawned by the agent.

    Returns:
        A formatted string listing all processes with their PID, command,
        elapsed time, and status.
    """
    if not _background_processes:
        return "No background processes running."

    lines = [f"Background processes ({len(_background_processes)}):"]
    for bg in _background_processes.values():
        d = bg.to_dict()
        lines.append(
            f"  [{d['pid']}] {d['status']} ({d['elapsed']}s) {d['command']}"
        )
    return "\n".join(lines)


async def kill_background_process(pid: str, **_: Any) -> str:
    """
    Terminate a background process by its Nexa-assigned PID.

    Args:
        pid: The process ID (e.g., ``"bg-a1b2c3d4"``).

    Returns:
        A confirmation message.

    Raises:
        ValueError: If the PID is not found or the process is already finished.
    """
    if not pid or not pid.strip():
        raise ValueError("pid is required")

    bg = _background_processes.get(pid)
    if bg is None:
        raise ValueError(f"no background process with PID '{pid}'")

    if bg.status != "running":
        raise ValueError(f"process '{pid}' is already {bg.status}")

    try:
        bg.process.kill()
        await bg.process.wait()
        bg.status = "killed"
        return f"Process {pid} killed."
    except ProcessLookupError:
        bg.status = "completed"
        return f"Process {pid} already finished."
    except Exception as e:
        bg.status = "error"
        return f"Error killing process {pid}: {e}"


async def generate_uuid(**_: Any) -> str:
    """
    Generate a random UUID v4 string.

    Returns:
        A 36-character UUID string (e.g., ``"550e8400-e29b-41d4-a716-446655440000"``).
    """
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# v2.1.0 hardening helpers
# ---------------------------------------------------------------------------
def _validate_cwd(cwd: Optional[str]) -> Path:
    """
    Validate and resolve the working directory against FORGE_WORKSPACE.

    Args:
        cwd: The requested working directory (may be ``None``).

    Returns:
        The resolved absolute :class:`~pathlib.Path`.

    Raises:
        ValueError: If ``cwd`` is outside the workspace.

    Example:
        >>> _validate_cwd(None)  # doctest: +SKIP
        PosixPath('.../forge-workspace')
    """
    if cwd is None:
        return FORGE_WORKSPACE.resolve()
    try:
        candidate = Path(cwd).resolve()
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid cwd '{cwd}': {exc}") from exc
    workspace = FORGE_WORKSPACE.resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(
            f"cwd '{cwd}' escapes the nexa workspace ({workspace}). "
            f"Terminal commands are project-scoped for safety."
        ) from exc
    return candidate


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """
    Kill the subprocess and its entire process tree.

    On Windows, uses ``taskkill /F /T /PID`` (force + tree).
    On Unix, uses ``os.killpg`` on the process group (if the process was
    started with ``start_new_session=True``).

    Args:
        proc: The :class:`asyncio.subprocess.Process` to kill.
    """
    pid = proc.pid
    if pid is None:
        return
    if sys.platform == "win32":
        # Windows: taskkill /F /T /PID <pid> — kills the whole tree.
        try:
            kill_proc = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(kill_proc.wait(), timeout=5.0)
            return
        except Exception:
            pass  # fall through to proc.kill()
    else:
        # Unix: kill the whole process group.
        try:
            os.killpg(os.getpgid(pid), 9)
            return
        except Exception:
            pass  # fall through to proc.kill()
    # Last resort: kill only the parent process.
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def _prune_completed_processes() -> int:
    """
    Remove completed/killed background processes from the registry.

    This prevents the module-level ``_background_processes`` dict from
    growing unboundedly over a long-running session.

    Returns:
        The number of processes pruned.
    """
    global _background_processes
    to_remove = [
        pid for pid, bg in _background_processes.items()
        if bg.status in ("completed", "killed", "error")
    ]
    for pid in to_remove:
        _background_processes.pop(pid, None)
    return len(to_remove)


# ---------------------------------------------------------------------------
# v3.0.0 — Terminal security: FORGE_HOME path protection
# ---------------------------------------------------------------------------
import re as _re

#: Patterns that indicate a command tries to access FORGE_HOME (~/.openforge/)
#: or its legacy alias (~/.nexa/) — both must stay blocked (post-rename backward
#: compat + migration protection).
#: Each is matched case-insensitively against the command string.
_PROTECTED_PATH_PATTERNS: list[str] = [
    r"~/\.openforge",        # ~/.openforge/...
    r"~/\.nexa",             # ~/.nexa/... (legacy)
    r"\$HOME/\.openforge",   # $HOME/.openforge/...
    r"\$HOME/\.nexa",        # $HOME/.nexa/... (legacy)
    r"\$FORGE_HOME",         # $FORGE_HOME/...
    r"\$NEXA_HOME",          # $NEXA_HOME/... (legacy)
    r"/\.openforge/",        # absolute /.openforge/ (Unix home-relative)
    r"/\.nexa/",             # absolute /.nexa/ (legacy)
    r"\.openforge/\.env",    # .openforge/.env (relative)
    r"\.nexa/\.env",         # .nexa/.env (relative legacy)
    r"\.openforge/memory",   # .openforge/memory (relative)
    r"\.nexa/memory",        # .nexa/memory (legacy)
    r"\.openforge/secrets",  # .openforge/secrets (relative)
    r"\.nexa/secrets",       # .nexa/secrets (legacy)
    r"\bopenforge\.db\b",    # the SQLite db filename (new)
    r"\bnexa\.db\b",         # the SQLite db filename (legacy)
    r"\.openforge/knowledge",
    r"\.nexa/knowledge",
    r"\.openforge/sessions",
    r"\.nexa/sessions",
    r"\.openforge/logs",
    r"\.nexa/logs",
    r"\.openforge/history",  # TUI history (may contain user messages)
    r"\.nexa/history",
    r"\.openforge/gateway\.pid",
    r"\.nexa/gateway\.pid",
]

#: Compiled patterns (case-insensitive).
_PROTECTED_COMPILED = [_re.compile(p, _re.IGNORECASE) for p in _PROTECTED_PATH_PATTERNS]


def is_protected_path_reference(command: str) -> bool:
    """
    Check whether ``command`` references a path inside ``FORGE_HOME``.

    This is the v3.0.0 security boundary: it prevents the LLM (via
    ``run_terminal_command``) from reading or writing files in
    ``~/.openforge/`` (or legacy ``~/.nexa/``) — where API keys, memory,
    secrets, and the SQLite DB live.

    Detected references include:
        - ``~/.openforge/...`` and ``~/.nexa/...``
        - ``$HOME/.openforge/...`` and ``$HOME/.nexa/...``
        - ``$FORGE_HOME/...`` and ``$NEXA_HOME/...``
        - ``.openforge/.env``, ``.openforge/memory``, ``.openforge/secrets``
          (and the ``.nexa/...`` legacy counterparts)
        - The literal filenames ``openforge.db`` and ``nexa.db``
        - Absolute paths that resolve inside ``FORGE_HOME`` (via ``Path.resolve()``).

    Args:
        command: The shell command string to inspect.

    Returns:
        ``True`` if the command references a protected path, else ``False``.

    Example:
        >>> is_protected_path_reference("cat ~/.openforge/.env")
        True
        >>> is_protected_path_reference("echo hello")
        False
        >>> is_protected_path_reference("ls forge-workspace/")
        False
    """
    if not command:
        return False
    # Pattern-based check (fast path).
    for pat in _PROTECTED_COMPILED:
        if pat.search(command):
            return True
    # Absolute-path resolution check (slower but thorough).
    # Extract anything that looks like an absolute path (Windows drive-letter
    # path or Unix absolute path) and check if it's inside FORGE_HOME.
    try:
        # Import the live FORGE_HOME (honors monkeypatch in tests).
        from openforge.config import FORGE_HOME as _FORGE_HOME
        home_resolved = _FORGE_HOME.resolve()
        # Match Windows drive-letter paths (C:\... or C:/...) or Unix absolute (/...).
        # Allow spaces inside the path (paths like C:\Users\Dearly Febriano\...).
        # Stop at shell metacharacters (|, &, ;, >, <, `) and quotes.
        abs_path_pattern = _re.compile(
            r"[A-Za-z]:[\\/][^|&;<>\`\"']+"
            r"|/[^|&;<>\`\"']+"
        )
        for token in abs_path_pattern.findall(command):
            token = token.strip().strip("'\"")
            if not token:
                continue
            try:
                resolved_token = Path(token).resolve()
                # Check if the token is inside FORGE_HOME.
                resolved_token.relative_to(home_resolved)
                return True
            except (ValueError, OSError):
                continue
    except Exception:
        # If anything goes wrong, fall back to the pattern-only result.
        pass
    return False


#: OpenAI function-calling schema for run_terminal_command.
RUN_TERMINAL_COMMAND_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute.",
        },
        "timeout": {
            "type": "number",
            "description": "Max execution time in seconds (default: 15, max: 60).",
        },
        "cwd": {
            "type": "string",
            "description": (
                "Working directory inside the workspace. Defaults to the "
                "workspace root. Must be inside FORGE_WORKSPACE."
            ),
        },
        "env": {
            "type": "object",
            "description": "Additional environment variables to merge with os.environ.",
            "additionalProperties": {"type": "string"},
        },
        "background": {
            "type": "boolean",
            "description": (
                "If true, the process runs in the background and its PID "
                "is returned immediately."
            ),
        },
    },
    "required": ["command"],
}
