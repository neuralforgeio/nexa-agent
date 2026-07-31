"""
Nexa Agent — File Patch Tool (Hardened v2.1.0)
==============================================

Provides the ``file_patch`` tool for applying unified diff patches to
files in the nexa workspace. This enables surgical file modifications
without rewriting the entire file.

Hardening (v2.1.0):
    - Uses the shared :func:`tools._paths.resolve_in_workspace` helper (DRY).
    - **Atomic write**: the patched content is written to a temp file in
      the same directory, then ``os.replace`` swaps it into place. If
      the write fails partway, the original file is left intact.
    - **No silent corruption**: when a hunk does not match the current
      file content, a :class:`ValueError` is raised (previously the hunk
      was silently appended at EOF).
    - **Backup**: creates a ``.bak`` copy before patching.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexa.config import NEXA_WORKSPACE
from tools._paths import resolve_in_workspace

# Re-export for backward compatibility.
_resolve_in_workspace = resolve_in_workspace


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
            exist, the path is a directory, the patch is malformed, a
            hunk does not match the current file content, or the atomic
            write fails.

    Example:
        >>> await file_patch(  # doctest: +SKIP
        ...     "notes.txt",
        ...     "--- a/notes.txt\\n+++ b/notes.txt\\n@@ -1,1 +1,1 @@\\n-old\\n+new\\n",
        ... )
        'Patched notes.txt: 1 hunk(s) applied. Backup: notes.txt.bak'
    """
    if not path or not path.strip():
        raise ValueError("path is required")
    if not patch or not patch.strip():
        raise ValueError("patch is required")

    full = resolve_in_workspace(path)
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    if full.is_dir():
        raise ValueError(f"'{path}' is a directory, not a file")

    # Read the original content.
    try:
        original_text = full.read_text("utf-8")
    except PermissionError as exc:
        raise ValueError(f"permission denied reading '{path}': {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not read '{path}': {exc}") from exc

    original_lines = original_text.splitlines(keepends=True)

    # Parse the patch into hunks.
    hunks = _parse_patch(patch)
    if not hunks:
        raise ValueError("no valid hunks found in patch")

    # Apply hunks (raises on mismatch — no silent corruption).
    result_lines = list(original_lines)
    hunks_applied = 0
    for hunk in hunks:
        result_lines = _apply_hunk(result_lines, hunk, path)
        hunks_applied += 1

    # Create backup (v3.1.0: rotate history, keep last 5 versions).
    backup_path = _rotate_backups(full)
    if backup_path is None:
        # File didn't exist before? Shouldn't happen here, but be safe.
        backup_path = full.with_suffix(full.suffix + ".bak")

    # Atomic write: write to a temp file in the same directory, then os.replace.
    new_content = "".join(result_lines)
    try:
        _atomic_write(full, new_content)
    except OSError as exc:
        # The original is still intact (backup exists + atomic write failed).
        raise ValueError(
            f"could not write patched content to '{path}': {exc}. "
            f"Original file is intact; backup at {backup_path.name}."
        ) from exc

    return f"Patched {path}: {hunks_applied} hunk(s) applied. Backup: {backup_path.name}"


def _atomic_write(target: Path, content: str) -> None:
    """
    Write ``content`` to ``target`` atomically.

    Writes to a temp file in the same directory, then ``os.replace`` swaps
    it into place. ``os.replace`` is atomic on POSIX and on Windows (for
    the same filesystem).

    Args:
        target:  The final target path.
        content: The text content to write.

    Raises:
        OSError: If the temp file creation, write, or rename fails.
    """
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile in the same directory so os.replace is atomic.
    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except OSError:
        # Clean up the temp file on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _parse_patch(patch: str) -> List[Dict[str, Any]]:
    """
    Parse a unified diff patch into hunks.

    Args:
        patch: The unified diff text.

    Returns:
        A list of hunk dicts with 'old_start', 'new_start', 'removes', 'adds'.
    """
    import re

    hunks: List[Dict[str, Any]] = []
    lines = patch.split("\n")
    current_hunk: Dict[str, Any] = None

    for line in lines:
        if line.startswith("@@"):
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


def _apply_hunk(
    lines: List[str],
    hunk: Dict[str, Any],
    path: str = "",
) -> List[str]:
    """
    Apply a single hunk to a list of lines.

    Args:
        lines: The current file lines.
        hunk:  The hunk dict with removes and adds.
        path:  The file path (for error messages).

    Returns:
        The modified list of lines.

    Raises:
        ValueError: If the hunk's removed lines do not match anywhere in
            the file (previously this silently appended at EOF, causing
            silent corruption).

    Example:
        >>> _apply_hunk(["old\\n"], {"removes": ["old"], "adds": ["new"]})
        ['new\\n']
    """
    removes = hunk["removes"]
    adds = hunk["adds"]

    # Pure insertion (no removes) — insert at the hunk's new_start, or at EOF.
    if not removes:
        new_lines = [a if a.endswith("\n") else a + "\n" for a in adds]
        # Insert before the line at index (new_start - 1), clamped.
        idx = max(0, min(len(lines), hunk.get("new_start", len(lines) + 1) - 1))
        return lines[:idx] + new_lines + lines[idx:]

    # v4.1.0: collect ALL positions where ``removes`` matches, then pick the
    # one closest to the hunk's declared ``new_start`` (line-number anchor).
    # If only one match exists anywhere, we take it — no ambiguity. If
    # several exist, the hunk's line number is the only way to disambiguate.
    remove_text = [r.rstrip("\n\r") for r in removes]
    anchor = int(hunk.get("new_start") or 0)

    matches: list[int] = []
    for i in range(len(lines)):
        ok = True
        for j, r in enumerate(remove_text):
            if i + j >= len(lines):
                ok = False
                break
            if lines[i + j].rstrip("\n\r") != r:
                ok = False
                break
        if ok:
            matches.append(i)

    if not matches:
        raise ValueError(
            f"hunk does not match file content (file: '{path}'). "
            f"Expected to find line(s): {remove_text[:3]}. "
            f"Refusing to apply — this would have silently corrupted the file."
        )

    if anchor:
        # new_start is 1-indexed (diff convention); convert to 0-indexed.
        target_idx = anchor - 1
        # Prefer the closest match to the declared line. If one is within a
        # ±5-line window, take it. Otherwise the hunk address is wrong.
        best = min(matches, key=lambda i: abs(i - target_idx))
        if abs(best - target_idx) > 5:
            raise ValueError(
                f"hunk claims to be at line {anchor} but the matching block "
                f"is at line {best + 1} (file: '{path}'). "
                f"Refusing to apply — regenerate the patch with correct line numbers."
            )
        chosen = best
    else:
        # No line anchor — only accept an unambiguous single match.
        if len(matches) > 1:
            raise ValueError(
                f"hunk matches {len(matches)} positions in '{path}' and "
                f"has no line-number anchor. Refusing to apply — "
                f"provide a unified-diff header (@@ -N,M +N,M @@)."
            )
        chosen = matches[0]

    add_lines = [a if a.endswith("\n") else a + "\n" for a in adds]
    return lines[:chosen] + add_lines + lines[chosen + len(removes):]


#: Maximum number of .bak versions to keep per file (v3.1.0 history rotation).
MAX_BACKUP_VERSIONS: int = 5


def _rotate_backups(target: Path) -> Optional[Path]:
    """
    Rotate the backup history for ``target`` and return the new backup path.

    Keeps the last ``MAX_BACKUP_VERSIONS`` backups, named ``<file>.bak``,
    ``<file>.bak.1``, ``<file>.bak.2``, etc. The oldest is deleted.

    Args:
        target: The file being patched.

    Returns:
        The path of the new (current) backup file, or ``None`` if the
        original file doesn't exist (nothing to back up).

    Example:
        >>> _rotate_backups(Path("notes.txt"))  # doctest: +SKIP
        PosixPath('notes.txt.bak')
    """
    if not target.exists():
        return None
    # Shift existing backups: .bak.4 → delete, .bak.3 → .bak.4, ..., .bak → .bak.1
    # Use shutil.move for cross-platform rename (Path.replace can fail on Windows
    # if the target exists with different permissions).
    # Iterate from oldest (highest index) down to the base .bak.
    for i in range(MAX_BACKUP_VERSIONS - 1, 0, -1):
        # Source: .bak.<i> for i>=1, else .bak (when i==0 we stop).
        if i >= 1:
            older = target.with_suffix(target.suffix + f".bak.{i}")
            # Destination: .bak.<i+1> (so .bak.1 → .bak.2, etc.)
            newer = target.with_suffix(target.suffix + f".bak.{i+1}")
        else:
            continue
        if older.exists():
            if newer.exists():
                try:
                    newer.unlink()
                except OSError:
                    pass
            try:
                shutil.move(str(older), str(newer))
            except OSError:
                pass
    # Now shift the base .bak → .bak.1 (if it exists).
    base_bak = target.with_suffix(target.suffix + ".bak")
    bak_1 = target.with_suffix(target.suffix + ".bak.1")
    if base_bak.exists():
        if bak_1.exists():
            try:
                bak_1.unlink()
            except OSError:
                pass
        try:
            shutil.move(str(base_bak), str(bak_1))
        except OSError:
            pass
    # Create the new .bak from the current file.
    backup_path = target.with_suffix(target.suffix + ".bak")
    try:
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass
        shutil.copy2(target, backup_path)
    except OSError:
        return None
    return backup_path


async def revert_file(path: str, version: int = 1, **_: Any) -> str:
    """
    Revert a file to a previous backup version (v3.1.0).

    Restores ``<file>.bak.<version>`` (or ``<file>.bak`` for version 1)
    as the current file, and rotates the current file into the backup
    history.

    Args:
        path:    Relative path to the file to revert.
        version: Backup version to restore (1 = most recent .bak, 2 = .bak.1, etc.).

    Returns:
        A confirmation message.

    Raises:
        ValueError: If the path escapes the workspace, the file doesn't
            exist, or the requested backup version doesn't exist.

    Example:
        >>> await revert_file("notes.txt", version=2)  # doctest: +SKIP
        'Reverted notes.txt to backup version 2.'
    """
    if not path or not path.strip():
        raise ValueError("path is required")
    full = resolve_in_workspace(path)
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    if full.is_dir():
        raise ValueError(f"'{path}' is a directory, not a file")

    # Resolve the backup path.
    if version == 1:
        backup = full.with_suffix(full.suffix + ".bak")
    else:
        backup = full.with_suffix(full.suffix + f".bak.{version - 1}")
    if not backup.exists():
        raise ValueError(
            f"backup version {version} not found for '{path}'. "
            f"Available versions: 1..{MAX_BACKUP_VERSIONS}."
        )

    # Restore backup → current file.
    # NOTE: do NOT rotate the current file into history here — that would
    # shift the .bak we're about to read from, making version 1 always point
    # to the content we're trying to replace. Just overwrite the target.
    try:
        shutil.copy2(backup, full)
    except OSError as exc:
        raise ValueError(f"could not revert '{path}': {exc}") from exc

    return f"Reverted {path} to backup version {version}."


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


#: OpenAI function-calling schema for revert_file (v3.1.0).
REVERT_FILE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path to the file to revert.",
        },
        "version": {
            "type": "integer",
            "description": (
                "Backup version to restore (1 = most recent .bak, "
                "2 = .bak.1, etc.). Default: 1."
            ),
            "default": 1,
            "minimum": 1,
            "maximum": 5,
        },
    },
    "required": ["path"],
}
