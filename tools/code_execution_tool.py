"""
OpenForge — Code Execution Tool (Project-Scoped Boundary + HITL)
==================================================================

Provides the ``code_execution`` tool for running Python code snippets
with a **project-scoped boundary** and an opt-in **Human-in-the-Loop
(HITL)** approval step.

Design decisions (honest, not over-claimed):
    - **Project-scoped, NOT a fully isolated sandbox**: code runs in a
      subprocess whose ``cwd`` is constrained to ``FORGE_WORKSPACE``.
      Paths outside the workspace are rejected. The subprocess still has
      host/network access — this is a boundary, not a sandbox.
    - **Cross-platform executable**: uses :data:`sys.executable` so the
      same Python interpreter that runs Nexa executes the code (works on
      Windows where ``python3`` is usually absent).
    - **HITL approval**: when ``requires_approval`` is ``True`` (the
      default), the ``approval_callback`` is invoked with the code. The
      callback returns ``True`` to allow execution, ``False`` to deny.
      If no callback is supplied (headless mode), the code is auto-denied
      — safe default.
    - **Robust kill**: on timeout, the subprocess and its children are
      killed via a process group (Unix: ``os.killpg``; Windows:
      ``taskkill /F /T /PID``).
    - **Timeout**: 10-second default, configurable up to 30 seconds.
    - **Output capping**: stdout and stderr capped to ``MAX_OUTPUT`` chars.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from openforge.config import FORGE_WORKSPACE

#: Maximum execution time in seconds.
DEFAULT_CODE_TIMEOUT: float = 10.0

#: Maximum allowed timeout.
MAX_CODE_TIMEOUT: float = 30.0

#: Maximum output length (characters per stream).
MAX_OUTPUT: int = 3000

#: Approval callback type — async callable that takes the code and returns
#: ``True`` to allow execution, ``False`` to deny.
ApprovalCallback = Callable[[str], Awaitable[bool]]

#: Timeout for the approval callback itself (seconds). If the user doesn't
#: respond within this window, the code is auto-denied.
APPROVAL_TIMEOUT: float = 30.0


async def code_execution(
    code: str,
    timeout: float = DEFAULT_CODE_TIMEOUT,
    requires_approval: bool = True,
    approval_callback: Optional[ApprovalCallback] = None,
    cwd: Optional[str] = None,
    **_: Any,
) -> str:
    """
    Execute a Python code snippet in a project-scoped subprocess.

    The code runs in a subprocess whose ``cwd`` is constrained to
    :data:`FORGE_WORKSPACE`. When ``requires_approval`` is ``True``, the
    ``approval_callback`` is invoked with the code; if it returns ``False``
    (or times out, or is ``None`` in headless mode), the code is denied.

    Args:
        code:               The Python code to execute.
        timeout:            Maximum execution time in seconds (default 10,
                            max 30).
        requires_approval:  If ``True``, invoke ``approval_callback`` before
                            executing (default ``True``).
        approval_callback:  Async callable ``async (code: str) -> bool``.
                            ``None`` means headless mode → auto-deny.
        cwd:                Optional override for the working directory.
                            Must be inside ``FORGE_WORKSPACE``; defaults to
                            ``FORGE_WORKSPACE`` itself.

    Returns:
        A formatted string with the exit code, stdout, and stderr. On
        denial, returns a message indicating the code was not approved.

    Raises:
        ValueError: If code is empty, timeout exceeds the maximum, or
                    ``cwd`` is outside the workspace.

    Example:
        >>> async def approve(code: str) -> bool:
        ...     print(f"About to run: {code}")
        ...     return True  # user typed 'y'
        >>> result = await code_execution(
        ...     "print(2 + 2)",
        ...     approval_callback=approve,
        ... )
        >>> "4" in result
        True
    """
    # --- Validate inputs ----------------------------------------------------
    if not code or not code.strip():
        raise ValueError("code is empty or whitespace-only")

    if timeout > MAX_CODE_TIMEOUT:
        raise ValueError(f"timeout {timeout}s exceeds maximum {MAX_CODE_TIMEOUT}s")

    # --- Resolve cwd (project-scoped boundary) -----------------------------
    workspace = FORGE_WORKSPACE.resolve()
    resolved_cwd = _validate_cwd(cwd, workspace)

    # --- HITL approval -----------------------------------------------------
    if requires_approval:
        approved = await _request_approval(code, approval_callback)
        if not approved:
            return ("[code_execution] Code was not approved for execution "
                    "(denied by user or headless auto-deny).")

    # --- Write code to a temp file -----------------------------------------
    # Use a temp file (not python -c) to handle multi-line code reliably.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="nexa_exec_", encoding="utf-8"
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        # --- Spawn the subprocess with a new process group -----------------
        # start_new_session=True on Unix, CREATE_NEW_PROCESS_GROUP on Windows.
        popen_kwargs: Dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": str(resolved_cwd),
        }
        if sys.platform == "win32":
            # Windows: CREATE_NEW_PROCESS_GROUP so we can taskkill the tree.
            popen_kwargs["creationflags"] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        else:
            # Unix: start_new_session creates a new session+process group.
            popen_kwargs["start_new_session"] = True

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            temp_path,
            **popen_kwargs,
        )

        # --- Wait with timeout ---------------------------------------------
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            # Robust kill: take down the whole process tree.
            await _kill_process_tree(proc)
            await proc.wait()
            return (f"[code_execution] Code timed out after {timeout}s "
                    f"and was killed (process tree terminated).")

        # --- Format output -------------------------------------------------
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT]

        parts = [f"exit code: {proc.returncode}"]
        if stdout:
            truncated = " [truncated]" if len(stdout_bytes) > MAX_OUTPUT else ""
            parts.append(f"stdout:{truncated}\n{stdout}")
        if stderr:
            truncated = " [truncated]" if len(stderr_bytes) > MAX_OUTPUT else ""
            parts.append(f"stderr:{truncated}\n{stderr}")
        if not stdout and not stderr:
            parts.append("(no output)")
        return "\n\n".join(parts)

    finally:
        # Clean up the temp file (best effort).
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_cwd(cwd: Optional[str], workspace: Path) -> Path:
    """
    Validate and resolve the working directory.

    Args:
        cwd:       The requested cwd (may be ``None``).
        workspace: The workspace root (must contain the resolved cwd).

    Returns:
        The resolved absolute :class:`~pathlib.Path`.

    Raises:
        ValueError: If ``cwd`` is outside the workspace.

    Example:
        >>> _validate_cwd(None, FORGE_WORKSPACE.resolve())  # doctest: +SKIP
        PosixPath('.../forge-workspace')
    """
    if cwd is None:
        return workspace
    try:
        candidate = Path(cwd).resolve()
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid cwd '{cwd}': {exc}") from exc
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(
            f"cwd '{cwd}' escapes the nexa workspace ({workspace}). "
            f"Code execution is project-scoped for safety."
        ) from exc
    return candidate


async def _request_approval(
    code: str,
    callback: Optional[ApprovalCallback],
) -> bool:
    """
    Request user approval for the code via the callback.

    Args:
        code:     The code about to be executed.
        callback: The async approval callback (may be ``None``).

    Returns:
        ``True`` if approved, ``False`` otherwise (including timeout and
        headless auto-deny).
    """
    if callback is None:
        # Headless mode — safe default is to deny.
        return False
    try:
        approved = await asyncio.wait_for(callback(code), timeout=APPROVAL_TIMEOUT)
        return bool(approved)
    except asyncio.TimeoutError:
        return False
    except Exception:
        # If the callback raises, treat as denied (don't crash the agent).
        return False


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """
    Kill the subprocess and its entire process tree.

    On Windows, uses ``taskkill /F /T /PID`` (force + tree).
    On Unix, uses ``os.killpg`` on the process group.

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


#: OpenAI function-calling schema for code_execution.
CODE_EXECUTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "The Python code to execute.",
        },
        "timeout": {
            "type": "number",
            "description": "Max execution time in seconds (default: 10, max: 30).",
        },
        "requires_approval": {
            "type": "boolean",
            "description": (
                "If true (default), the user is asked to approve the code "
                "before execution. Set to false to skip approval (use with "
                "caution — the code has project-scoped file access)."
            ),
        },
        "cwd": {
            "type": "string",
            "description": (
                "Optional working directory inside the workspace. Defaults "
                "to the workspace root."
            ),
        },
    },
    "required": ["code"],
}
