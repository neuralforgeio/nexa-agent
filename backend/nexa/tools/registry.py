"""
Nexa Agent — Tool Registry & Dispatcher
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import time
from typing import Any, Dict, List, Optional

from .base import NexaTool, ToolResult


class ToolRegistry:
    """Central registry that owns tool lifecycle."""

    def __init__(self):
        self._tools: Dict[str, NexaTool] = {}

    def register(self, tool: NexaTool) -> "ToolRegistry":
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        return self

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Optional[NexaTool]:
        return self._tools.get(name)

    def list(self) -> List[NexaTool]:
        return list(self._tools.values())

    def schemas(self) -> List[Dict[str, Any]]:
        return [t.get_schema() for t in self.list()]

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """OpenAI function-calling schema array."""
        return [t.get_openai_schema() for t in self.list()]

    def describe(self) -> str:
        """Human-readable summary for the system prompt."""
        lines = []
        for t in self.list():
            params = ", ".join(
                f"{k}: {v.type}{' (required)' if v.required else ''}"
                for k, v in t.parameters.items()
            )
            lines.append(f"- {t.name} — {t.description} [params: {params or 'none'}]")
        return "\n".join(lines)

    async def execute(self, name: str, args: Dict[str, Any]) -> ToolResult:
        """Dispatch a tool request, capturing timing. Never raises."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(name, False, f"Unknown tool: {name}")
        start = time.time()
        try:
            result = await tool.execute(args or {})
            if not result.duration_ms:
                result.duration_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            return ToolResult(
                name,
                False,
                f"Tool '{name}' crashed: {e}",
                int((time.time() - start) * 1000),
            )
