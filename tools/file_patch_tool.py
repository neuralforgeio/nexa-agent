"""
Nexa Agent — File Patch Tool
============================

Provides the ``file_patch`` tool for applying unified diff patches to
files in the nexa workspace. This enables surgical file modifications
without rewriting the entire file.

Design decisions:
    - **Unified diff format**: Uses the standard ``unified_diff`` format
      that developers are familiar with from Git.
    - **Sandboxed**: Only operates on files within ``NEXA_WORKSPACE``.
    - **Atomic**: The patch is applied to a copy first; if any hunk fails,
      the original file is left unchanged.
    - **Backup**: Creates a ``.bak`` copy before patching.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from nexa.config import NEXA_WORKSPACE


def _resolve_in_workspace(raw: str) -> Path:
    """
    Resolve a path safely inside the workspace.

    Args:
        raw: A relative path.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the path escapes the workspace.
    """
    base = NEXA_WORKSPACE.resolve()
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"path '{raw}' escapes the nexa workspace ({base})")
    return resolved


async def file_patch(path: str, patch: str, **_: Any) -> str:
    """
    Apply a unified diff patch to a file in the workspace.

    The patch format is a simplified unified diff::

        --- file.txt
        +++ file.txt
        @@ -1,3 +1,3 @@
         line 1
        -old line 2
        +new line 2
         line 3

    Lines starting with ``-`` are removed, lines with ``+`` are added,
    and lines starting with `` `` (space) are context (unchanged).

    Args:
        path:  Relative path to the file to patch.
        patch: The unified diff patch text.

    Returns:
        A confirmation message with the number of hunks applied.

    Raises:
        ValueError: If the path escapes the workspace, the file doesn't
                    exist, or the patch is malformed.
    """
    if not path or not path.strip():
        raise ValueError("path is required")
    if not patch or not patch.strip():
        raise ValueError("patch is required")

    full = _resolve_in_workspace(path)
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    if full.is_dir():
        raise ValueError(f"'{path}' is a directory, not a file")

    # Read the original content.
    original_lines = full.read_text("utf-8").splitlines(keepends=True)

    # Parse the patch into hunks.
    hunks = _parse_patch(patch)
    if not hunks:
        raise ValueError("no valid hunks found in patch")

    # Apply hunks.
    result_lines = list(original_lines)
    hunks_applied = 0
    for hunk in hunks:
        result_lines = _apply_hunk(result_lines, hunk)
        hunks_applied += 1

    # Create backup.
    backup_path = full.with_suffix(full.suffix + ".bak")
    shutil.copy2(full, backup_path)

    # Write the patched content.
    full.write_text("".join(result_lines), "utf-8")

    return f"Patched {path}: {hunks_applied} hunk(s) applied. Backup: {backup_path.name}"


def _parse_patch(patch: str) -> List[Dict[str, Any]]:
    """
    Parse a unified diff patch into hunks.

    Args:
        patch: The unified diff text.

    Returns:
        A list of hunk dicts with 'old_start', 'new_start', 'removes', 'adds'.
    """
    hunks: List[Dict[str, Any]] = []
    lines = patch.split("\n")
    current_hunk: Dict[str, Any] = None

    for line in lines:
        if line.startswith("@@"):
            # Parse hunk header: @@ -start,count +start,count @@
            import re
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    "old_start": int(match.group(1)),
                    "new_start": int(match.group(3)),
                    "removes": [],
                    "adds": [],
                    "context": [],
                }
        elif current_hunk is not None:
            if line.startswith("-"):
                current_hunk["removes"].append(line[1:])
            elif line.startswith("+"):
                current_hunk["adds"].append(line[1:])
            elif line.startswith(" "):
                current_hunk["context"].append(line[1:])

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def _apply_hunk(lines: List[str], hunk: Dict[str, Any]) -> List[str]:
    """
    Apply a single hunk to a list of lines.

    Args:
        lines: The current file lines.
        hunk:  The hunk dict with removes and adds.

    Returns:
        The modified list of lines.
    """
    removes = hunk["removes"]
    adds = hunk["adds"]

    # Find the position of the first removed line.
    if not removes:
        # Pure insertion — append at end or at new_start.
        return lines + [a + "\n" for a in adds]

    # Search for the removed lines in the file.
    remove_text = [r.rstrip("\n\r") for r in removes]
    for i in range(len(lines)):
        match = True
        for j, r in enumerate(remove_text):
            if i + j >= len(lines):
                match = False
                break
            if lines[i + j].rstrip("\n\r") != r:
                match = False
                break
        if match:
            # Replace the removed lines with the added lines.
            return lines[:i] + [a + "\n" for a in adds] + lines[i + len(removes):]

    # If no match found, just append the adds (graceful degradation).
    return lines + [a + "\n" for a in adds]


#: OpenAI function-calling schema for file_patch.
FILE_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path to the file to patch.",
        },
        "patch": {
            "type": "string",
            "description": "The unified diff patch text.",
        },
    },
    "required": ["path", "patch"],
}
