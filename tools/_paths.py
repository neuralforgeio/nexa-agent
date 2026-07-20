"""
Nexa Agent — Shared Path Helpers
================================

Shared helpers for resolving user-supplied paths safely inside the
``NEXA_WORKSPACE`` directory. Used by every filesystem tool to prevent
arbitrary host access.

This module exists to eliminate the DRY violation where
``_resolve_in_workspace`` was duplicated between :mod:`tools.file_tools`
and :mod:`tools.file_patch_tool`.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path

from nexa.config import NEXA_WORKSPACE

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
    base = NEXA_WORKSPACE.resolve()
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"path '{raw}' escapes the nexa workspace ({base})"
        ) from exc
    return resolved
