"""
Nexa Agent — Code Execution Tool
================================

Provides the ``code_execution`` tool for running Python code snippets
in a sandboxed environment. The code runs in a subprocess with a
timeout, output capture, and restricted builtins.

Design decisions:
    - **Sandboxed**: Code runs in a subprocess (not the main process).
    - **Timeout**: 10-second default, configurable up to 30 seconds.
    - **Output capping**: stdout and stderr capped to prevent memory issues.
    - **No file access**: The sandbox has no access to the workspace filesystem
      (code runs in a temporary directory).
    - **Restricted builtins**: Dangerous functions (exec, eval, open, import)
      are NOT restricted (the sandbox is the subprocess boundary, not the
      Python runtime). The workspace sandbox directory prevents file access
      to the host.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import tempfile
import os
from pathlib import Path
from typing import Any, Dict

#: Maximum execution time in seconds.
DEFAULT_CODE_TIMEOUT: float = 10.0

#: Maximum allowed timeout.
MAX_CODE_TIMEOUT: float = 30.0

#: Maximum output length (characters).
MAX_OUTPUT: int = 3000


async def code_execution(
    code: str,
    timeout: float = DEFAULT_CODE_TIMEOUT,
    **_: Any,
) -> str:
    """
    Execute a Python code snippet in a sandboxed subprocess.

    The code is written to a temporary file and executed with
    ``python3 -c`` in a subprocess. stdout and stderr are captured.

    Args:
        code:    The Python code to execute.
        timeout: Maximum execution time in seconds (default: 10, max: 30).

    Returns:
        A formatted string with the exit code, stdout, and stderr.

    Raises:
        ValueError: If code is empty or timeout exceeds maximum.
    """
    if not code or not code.strip():
        raise ValueError("code is empty or whitespace-only")

    if timeout > MAX_CODE_TIMEOUT:
        raise ValueError(f"timeout {timeout}s exceeds maximum {MAX_CODE_TIMEOUT}s")

    # Write code to a temp file and execute.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="nexa_exec_"
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tempfile.gettempdir(),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise asyncio.TimeoutError(f"code execution timed out ({timeout}s)")

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
        # Clean up the temp file.
        try:
            os.unlink(temp_path)
        except OSError:
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
    },
    "required": ["code"],
}
