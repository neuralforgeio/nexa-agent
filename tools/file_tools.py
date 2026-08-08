"""
Nexa Agent — File Tools (Hardened v2.1.0)
=========================================

Filesystem tools (``read_file``, ``write_file``) sandboxed to the
``FORGE_WORKSPACE`` directory to prevent arbitrary host access.

Hardening (v2.1.0):
    - Uses the shared :func:`tools._paths.resolve_in_workspace` helper (DRY).
    - ``write_file`` enforces a 1MB size cap and an ``is_dir`` guard.
    - ``write_file`` catches ``PermissionError`` / ``IsADirectoryError``
      / ``OSError`` specifically and returns a friendly ValueError.
    - ``read_file`` distinguishes FileNotFoundError / PermissionError /
      IsADirectoryError for clearer error messages.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from pathlib import Path
from typing import Any

from openforge.config import FORGE_WORKSPACE
from tools._paths import MAX_FILE_SIZE, resolve_in_workspace

# Re-export for backward compatibility (file_tools._resolve_in_workspace).
_resolve_in_workspace = resolve_in_workspace


async def read_file(path: str, **_: Any) -> str:
    """
    Read a text file from the workspace.

    M-10: auto-detect file type by extension and dispatch to the dedicated
    reader — .pdf → read_pdf, .docx → read_docx, .xlsx → read_xlsx,
    .pptx → read_pptx; everything else falls back to plain text.

    Args:
        path: Relative path to the file inside the workspace.

    Returns:
        The file content as a string (truncated to 4000 chars if larger).

    Raises:
        ValueError: If the path escapes the workspace, the file is a
            directory, the file is not found, the user lacks permission,
            or the file exceeds 100KB.

    Example:
        >>> await read_file("notes.txt")  # doctest: +SKIP
        'this is the file content'
    """
    try:
        full = resolve_in_workspace(path)
    except ValueError:
        raise

    # Extension-based multimodal dispatch (M-10).
    suffix = full.suffix.lower()
    if suffix == ".pdf":
        from tools.core.read_pdf import read_pdf

        return await read_pdf(path)
    if suffix == ".docx":
        from tools.core.read_docx import read_docx

        return await read_docx(path)
    if suffix == ".xlsx":
        from tools.core.read_xlsx import read_xlsx

        return await read_xlsx(path)
    if suffix == ".pptx":
        from tools.core.read_pptx import read_pptx

        return await read_pptx(path)

    # Specific checks for clearer error messages.
    if not full.exists():
        raise ValueError(f"file not found: '{path}'")
    if full.is_dir():
        raise ValueError(f"'{path}' is a directory, not a file")

    try:
        size = full.stat().st_size
    except PermissionError as exc:
        raise ValueError(f"permission denied reading '{path}': {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not stat '{path}': {exc}") from exc

    if size > 100_000:
        raise ValueError(f"file too large ({size} bytes, max 100KB)")

    try:
        content = full.read_text("utf-8")
    except PermissionError as exc:
        raise ValueError(f"permission denied reading '{path}': {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"file '{path}' is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not read '{path}': {exc}") from exc

    if len(content) > 4000:
        content = content[:4000] + f"\n…[truncated, {len(content)} chars total]"
    return content


async def write_file(path: str, content: str, **_: Any) -> str:
    """
    Write text content to a file in the workspace.

    Creates parent directories if they don't exist. Overwrites the file
    if it already exists.

    Args:
        path:    Relative path to the file inside the workspace.
        content: The text content to write (max 1MB).

    Returns:
        A confirmation message with the byte count.

    Raises:
        ValueError: If the path escapes the workspace, the target is an
            existing directory, the content exceeds 1MB, or a permission
            / OS error occurs during the write.

    Example:
        >>> await write_file("notes.txt", "hello")  # doctest: +SKIP
        'wrote 5 bytes to notes.txt'
    """
    # Size cap.
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise ValueError(
            f"content too large ({len(encoded)} bytes, max {MAX_FILE_SIZE} bytes = 1MB)"
        )

    full = resolve_in_workspace(path)

    # Guard against writing to an existing directory.
    if full.exists() and full.is_dir():
        raise ValueError(f"cannot write file: '{path}' is an existing directory")

    # v4.1.0: atomic write — stage to a temp file, then os.replace() over
    # the destination. Prevents a torn file if the process is interrupted
    # mid-write (Ctrl+C, kill, power loss).
    tmp = full.with_name(full.name + ".nexa.tmp")
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(content, "utf-8")
        os.replace(str(tmp), str(full))
    except PermissionError as exc:
        raise ValueError(f"permission denied writing '{path}': {exc}") from exc
    except IsADirectoryError as exc:
        raise ValueError(f"'{path}' is a directory, not a file: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"could not write '{path}': {exc}") from exc
    finally:
        # Best-effort cleanup if the replace never ran (e.g. permission
        # error raised while staging the temp file).
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    return f"wrote {len(encoded)} bytes to {path}"
