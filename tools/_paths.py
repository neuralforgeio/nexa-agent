"""
Nexa Agent — Shared Path Helpers
================================

Shared helpers for resolving user-supplied paths safely inside the
``FORGE_WORKSPACE`` directory. Used by every filesystem tool to prevent
arbitrary host access.

This module exists to eliminate the DRY violation where
``_resolve_in_workspace`` was duplicated between :mod:`tools.file_tools`
and :mod:`tools.file_patch_tool`.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path

from openforge.config import FORGE_WORKSPACE

#: Maximum file size the tools will read/write (1 MB).
MAX_FILE_SIZE: int = 1_048_576


def resolve_in_workspace(raw: str) -> Path:
    """
    Resolve a user-supplied path safely inside the workspace.

    Args:
        raw: A relative path (e.g. ``"notes.txt"`` or ``"src/app.py"``).

    Returns:
        The resolved absolute :class:`~pathlib.Path`.

    Raises:
        ValueError: If the path escapes the workspace (via ``..`` or an
            absolute path outside the workspace root).

    Example:
        >>> resolve_in_workspace("notes.txt")  # doctest: +SKIP
        PosixPath('/home/user/.nexa/workspace/notes.txt')
        >>> resolve_in_workspace("../../etc/passwd")  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        ValueError: path '../../etc/passwd' escapes the nexa workspace (...)
    """
    # v4.2.1-fix: reject control characters and NUL. On Windows + Linux
    # paths, a NUL byte (``\x00``) is a recognised path terminator trick —
    # accepted by some OS calls before erroring on downstream consumers.
    # We reject any byte < 0x20 (excluding tab/newline/carriage return) or
    # 0x7f to cut off smuggling attempts at the boundary.
    if not raw or not raw.strip():
        raise ValueError("path cannot be empty or whitespace-only")
    bad = [c for c in raw if ord(c) < 0x20 and c not in ("\t",)]
    if bad:
        raise ValueError(
            f"invalid control character in path: U+{ord(bad[0]):04X}"
        )
    if "\x00" in raw or "\ufffd" in raw:
        raise ValueError("path contains null byte or invalid marker")

    # Reject URL-encoded traversal (e.g. "..%2f", "..%5c", "%2e%2e").
    lowered = raw.lower()
    if "%2f" in lowered or "%5c" in lowered or "%2e" in lowered:
        decoded = raw.replace("%2f", "/").replace("%5c", "\\").replace("%2e", ".")
        if ".." in decoded.replace("\\", "/"):
            raise ValueError(f"encoded traversal in path: '{raw}'")

    base = FORGE_WORKSPACE.resolve()
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"path '{raw}' escapes the nexa workspace ({base})"
        ) from exc
    return resolved
