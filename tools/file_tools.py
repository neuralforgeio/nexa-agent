"""
Nexa Agent — File Tools
=======================

Filesystem tools (``read_file``, ``write_file``) sandboxed to the
``NEXA_WORKSPACE`` directory to prevent arbitrary host access.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path
from typing import Any

from nexa.config import NEXA_WORKSPACE


def _resolve_in_workspace(raw: str) -> Path:
    """
    Resolve a user-supplied path safely inside the workspace.

    Args:
        raw: A relative path (e.g. ``"notes.txt"`` or ``"src/app.py"``).

    Returns:
        The resolved absolute :class:`~pathlib.Path`.

    Raises:
        ValueError: If the path escapes the workspace (via ``..`` or an
            absolute path).
    """
    base = NEXA_WORKSPACE.resolve()
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"path '{raw}' escapes the nexa workspace ({base})"
        ) from exc
    return resolved


async def read_file(path: str, **_: Any) -> str:
    """
    Read a text file from the workspace.

    Args:
        path: Relative path to the file inside the workspace.

    Returns:
        The file content as a string (truncated to 4000 chars if larger).

    Raises:
        ValueError: If the path escapes the workspace or the file cannot be read.
    """
    try:
        full = _resolve_in_workspace(path)
        if full.is_dir():
            raise ValueError(f"'{path}' is a directory, not a file")
        if not full.exists():
            raise ValueError(f"file not found: '{path}'")
        size = full.stat().st_size
        if size > 100_000:
            raise ValueError(f"file too large ({size} bytes, max 100KB)")
        content = full.read_text("utf-8")
        if len(content) > 4000:
            content = content[:4000] + f"\n…[truncated, {len(content)} chars total]"
        return content
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"could not read '{path}': {e}")


async def write_file(path: str, content: str, **_: Any) -> str:
    """
    Write text content to a file in the workspace.

    Creates parent directories if they don't exist. Overwrites the file
    if it already exists.

    Args:
        path:    Relative path to the file inside the workspace.
        content: The text content to write.

    Returns:
        A confirmation message with the byte count.

    Raises:
        ValueError: If the path escapes the workspace.
    """
    full = _resolve_in_workspace(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, "utf-8")
    return f"wrote {len(content.encode('utf-8'))} bytes to {path}"
