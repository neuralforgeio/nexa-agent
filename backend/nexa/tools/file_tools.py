"""
Nexa Agent — File Tools (read, write, list)
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from pathlib import Path
from typing import Any, Dict

from ..constants import NEXA_WORKSPACE
from .base import NexaTool, ToolParameter, ToolResult


def _resolve_in_workspace(raw: str) -> Path:
    """Resolve a path safely inside the workspace, rejecting escapes."""
    base = NEXA_WORKSPACE.resolve()
    resolved = (base / raw).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"path '{raw}' escapes the nexa workspace ({base})")
    return resolved


class ReadFileTool(NexaTool):
    name = "read_file"
    description = (
        "Read the contents of a text file inside the nexa workspace. "
        "Path is relative to the workspace root. Returns content (truncated to 4000 chars)."
    )
    parameters = {
        "path": ToolParameter("string", "Relative path to the file.", required=True),
    }

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        rel = str(args.get("path", "")).strip()
        if not rel:
            return ToolResult(self.name, False, "path is required")
        try:
            full = _resolve_in_workspace(rel)
            if full.is_dir():
                return ToolResult(self.name, False, f"'{rel}' is a directory")
            size = full.stat().st_size
            if size > 100_000:
                return ToolResult(self.name, False, f"file too large ({size} bytes)")
            content = full.read_text("utf-8")
            if len(content) > 4000:
                content = content[:4000] + f"\n…[truncated, {len(content)} chars total]"
            return ToolResult(self.name, True, content)
        except Exception as e:
            return ToolResult(self.name, False, f"could not read '{rel}': {e}")


class WriteFileTool(NexaTool):
    name = "write_file"
    description = (
        "Write text content to a file inside the nexa workspace. "
        "Overwrites if exists, creates parent dirs if needed."
    )
    parameters = {
        "path": ToolParameter("string", "Relative path to the file.", required=True),
        "content": ToolParameter("string", "The text content to write.", required=True),
    }

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        rel = str(args.get("path", "")).strip()
        content = str(args.get("content", ""))
        if not rel:
            return ToolResult(self.name, False, "path is required")
        try:
            full = _resolve_in_workspace(rel)
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, "utf-8")
            return ToolResult(self.name, True, f"wrote {len(content.encode('utf-8'))} bytes to {rel}")
        except Exception as e:
            return ToolResult(self.name, False, f"could not write '{rel}': {e}")


class ListDirTool(NexaTool):
    name = "list_dir"
    description = "List files and subdirectories in a workspace directory. Pass '.' for root."
    parameters = {
        "path": ToolParameter("string", "Relative directory path. Default '.'.", required=False),
    }

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        rel = str(args.get("path", ".")).strip() or "."
        try:
            full = _resolve_in_workspace(rel)
            entries = sorted(full.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            if not entries:
                return ToolResult(self.name, True, f"'{rel}' is empty")
            lines = [f"{'📁' if e.is_dir() else '📄'} {e.name}" for e in entries]
            return ToolResult(
                self.name, True,
                f"contents of '{rel}' ({len(entries)} entries):\n" + "\n".join(lines),
            )
        except Exception as e:
            return ToolResult(self.name, False, f"could not list '{rel}': {e}")
