"""
Nexa Agent — Memory File Manager
================================

Manages persistent memory files at ``~/.nexa/memory/``:

    - ``MEMORY.md`` — Agent notes and accumulated insights.
    - ``USER.md``   — User profile (preferences, facts about the user).

These files provide a human-readable, file-based memory layer that
complements the SQLite memory store. Users can inspect and edit them
directly, and the agent reads them on startup to inject context into
the system prompt.

The file format is Markdown with a simple structure::

    # Memory
    ## Preferences
    - Prefers concise answers
    ## Facts
    - User's name is Dearly

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path
from typing import Any, Dict, List

from nexa.config import NEXA_HOME


#: The directory where memory files live.
MEMORY_DIR: Path = NEXA_HOME / "memory"

#: The agent notes file (insights, skills, general knowledge).
MEMORY_FILE: Path = MEMORY_DIR / "MEMORY.md"

#: The user profile file (preferences, facts about the user).
USER_FILE: Path = MEMORY_DIR / "USER.md"

#: Optional root-level USER.md at ``~/.nexa/USER.md`` overrides the
#: per-memory copy if present (v4.1.0). Users can edit the root file for
#: quick tweaks without digging into the memory subdirectory.
USER_FILE_ROOT: Path = NEXA_HOME / "USER.md"

#: Optional root-level procedures playbook at ``~/.nexa/PROCEDURES.md``.
PROCEDURES_FILE: Path = NEXA_HOME / "PROCEDURES.md"


def ensure_memory_dir() -> Path:
    """
    Ensure the ``~/.nexa/memory/`` directory exists.

    Returns:
        The :class:`~pathlib.Path` to the memory directory.
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR


def read_memory_file() -> str:
    """
    Read the contents of ``MEMORY.md``.

    Returns:
        The file content as a string, or an empty string if the file
        does not exist.
    """
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text(encoding="utf-8")
    return ""


def read_user_file() -> str:
    """
    Read the contents of ``USER.md``.

    Resolution order (v4.1.0):
      1. ``~/.nexa/USER.md`` (root-level, easier for users to edit), if
         it exists and is non-empty.
      2. ``~/.nexa/memory/USER.md``.

    Returns:
        The file content as a string, or an empty string if the file
        does not exist.
    """
    if USER_FILE_ROOT.exists():
        root = USER_FILE_ROOT.read_text(encoding="utf-8").strip()
        if root:
            return root
    if USER_FILE.exists():
        return USER_FILE.read_text(encoding="utf-8")
    return ""


def read_procedures_file() -> str:
    """
    Read the user's procedures playbook at ``~/.nexa/PROCEDURES.md``.

    Returns:
        The file contents (empty string if not present). Injected into
        the system prompt so procedural memory guides tool selection.
    """
    if PROCEDURES_FILE.exists():
        return PROCEDURES_FILE.read_text(encoding="utf-8")
    return ""


def write_memory_file(content: str) -> None:
    """
    Write content to ``MEMORY.md`` (overwrites existing).

    Args:
        content: The full Markdown content to write.
    """
    ensure_memory_dir()
    MEMORY_FILE.write_text(content, encoding="utf-8")


def write_user_file(content: str) -> None:
    """
    Write content to ``USER.md`` (overwrites existing).

    Args:
        content: The full Markdown content to write.
    """
    ensure_memory_dir()
    USER_FILE.write_text(content, encoding="utf-8")


def append_to_memory(entry: str, kind: str = "insight") -> None:
    """
    Append a single entry to ``MEMORY.md`` under the appropriate section.

    The file is organized into sections by kind. If the section doesn't
    exist, it is created. If the file doesn't exist, it is initialized.

    Args:
        entry: The memory text to append.
        kind:  The memory kind (``"insight"``, ``"preference"``,
               ``"fact"``, ``"skill"``). Determines which section the
               entry goes under.
    """
    ensure_memory_dir()
    current = read_memory_file()
    section_header = f"## {kind.capitalize()}s"

    lines = current.split("\n") if current else ["# Nexa Agent Memory", ""]

    # Find or create the section.
    section_index = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_index = i
            break

    if section_index is None:
        # Append a new section at the end.
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(section_header)
        lines.append(f"- {entry}")
    else:
        # Insert after the section header.
        lines.insert(section_index + 1, f"- {entry}")

    write_memory_file("\n".join(lines))


def append_to_user(entry: str, kind: str = "preference") -> None:
    """
    Append a single entry to ``USER.md`` under the appropriate section.

    Args:
        entry: The user fact/preference to append.
        kind:  The entry kind (``"preference"`` or ``"fact"``).
    """
    ensure_memory_dir()
    current = read_user_file()
    section_header = f"## {kind.capitalize()}s"

    lines = current.split("\n") if current else ["# User Profile", ""]

    section_index = None
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_index = i
            break

    if section_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(section_header)
        lines.append(f"- {entry}")
    else:
        lines.insert(section_index + 1, f"- {entry}")

    write_user_file("\n".join(lines))


def build_memory_file_digest() -> str:
    """
    Build a combined digest of MEMORY.md and USER.md for the system prompt.

    Reads both files and formats them into a single string that can be
    injected into the system prompt so the agent has context from
    previous sessions.

    Returns:
        A formatted string with both files' contents, or an empty string
        if neither file exists.
    """
    parts: List[str] = []

    memory_content = read_memory_file()
    if memory_content.strip():
        parts.append(f"# Agent Memory File\n{memory_content.strip()}")

    user_content = read_user_file()
    if user_content.strip():
        parts.append(f"# User Profile\n{user_content.strip()}")

    procedures = read_procedures_file()
    if procedures.strip():
        parts.append(f"# User Procedures\n{procedures.strip()}")

    return "\n\n".join(parts) if parts else ""


def sync_db_to_files(memories: List[Dict[str, Any]]) -> None:
    """
    Synchronize DB memories to the MEMORY.md file.

    This rebuilds the file from the DB memory list, organizing entries
    by kind into sections. Call this after bulk memory operations or
    on startup to ensure the file reflects the DB state.

    Args:
        memories: A list of memory dicts from
                  :meth:`~nexa.state.ConversationDB.list_memories`.
    """
    if not memories:
        return

    ensure_memory_dir()

    # Group by kind.
    by_kind: Dict[str, List[str]] = {}
    for m in memories:
        kind = m.get("kind", "insight")
        by_kind.setdefault(kind, []).append(m["content"])

    lines = ["# Nexa Agent Memory", ""]
    for kind in ("insight", "preference", "fact", "skill"):
        if kind in by_kind:
            lines.append(f"## {kind.capitalize()}s")
            for entry in by_kind[kind]:
                lines.append(f"- {entry}")
            lines.append("")

    write_memory_file("\n".join(lines))
