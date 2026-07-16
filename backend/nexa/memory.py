"""
Nexa Agent — Memory Manager
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path
from typing import List

from .constants import NEXA_DIRS, NEXA_MEMORY_FILES


class MemoryManager:
    """Manages ~/.nexa/memory/MEMORY.md and USER.md."""

    def __init__(self):
        self.memory_dir = NEXA_DIRS["memory"]
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_file(self) -> Path:
        return self.memory_dir / NEXA_MEMORY_FILES["memory"]

    @property
    def user_file(self) -> Path:
        return self.memory_dir / NEXA_MEMORY_FILES["user"]

    def read_memory(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text("utf-8")
        return ""

    def read_user(self) -> str:
        if self.user_file.exists():
            return self.user_file.read_text("utf-8")
        return ""

    def append_memory(self, entry: str) -> None:
        current = self.read_memory()
        self.memory_file.write_text(current + f"\n- {entry}", "utf-8")

    def append_user(self, entry: str) -> None:
        current = self.read_user()
        self.user_file.write_text(current + f"\n- {entry}", "utf-8")

    def digest(self) -> str:
        """Render a combined digest for the system prompt."""
        memory = self.read_memory()
        user = self.read_user()
        parts = []
        if user:
            parts.append(f"## User profile\n{user}")
        if memory:
            parts.append(f"## Agent notes\n{memory}")
        if not parts:
            return "(no memories stored yet)"
        return "\n\n".join(parts)
