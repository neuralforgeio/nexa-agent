"""
Nexa Agent — Tool Base
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ToolParameter:
    """A single tool parameter descriptor."""

    def __init__(
        self,
        param_type: str,
        description: str,
        required: bool = False,
    ):
        self.type = param_type
        self.description = description
        self.required = required


class NexaTool(ABC):
    """Abstract contract every Nexa tool implements."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, ToolParameter] = {}
    category: str = "utility"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {k: v.__dict__ for k, v in self.parameters.items()},
        }

    def get_openai_schema(self) -> Dict[str, Any]:
        """OpenAI function-calling schema."""
        properties = {}
        required = []
        for key, param in self.parameters.items():
            properties[key] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(key)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> "ToolResult":
        """Execute the tool. Must never raise — return ok=False on failure."""
        ...


class ToolResult:
    """Structured result of executing a tool."""

    def __init__(self, tool: str, ok: bool, output: str, duration_ms: int = 0):
        self.tool = tool
        self.ok = ok
        self.output = output
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "output": self.output,
            "duration_ms": self.duration_ms,
        }
