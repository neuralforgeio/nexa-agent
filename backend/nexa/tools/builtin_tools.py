"""
Nexa Agent — Built-in Tools (echo, calculate, get_time, generate_uuid)
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
import uuid
from datetime import datetime
from typing import Any, Dict

from .base import NexaTool, ToolParameter, ToolResult


class EchoTool(NexaTool):
    name = "echo"
    description = "Echo the provided text back. Useful for debugging."
    parameters = {"text": ToolParameter("string", "The text to echo.", required=True)}

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult(self.name, True, str(args.get("text", "")))


class CalculateTool(NexaTool):
    name = "calculate"
    description = "Evaluate a math expression with +, -, *, /, parentheses and decimals."
    parameters = {
        "expression": ToolParameter("string", "The arithmetic expression.", required=True),
    }
    _SAFE = re.compile(r"^[\d\s+\-*/().]+$")

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        expr = str(args.get("expression", "")).strip()
        if not expr:
            return ToolResult(self.name, False, "empty expression")
        if not self._SAFE.match(expr):
            return ToolResult(self.name, False, "invalid characters in expression")
        try:
            result = eval(expr, {"__builtins__": {}}, {})
            if not isinstance(result, (int, float)):
                return ToolResult(self.name, False, "result is not a number")
            return ToolResult(self.name, True, f"{expr} = {result}")
        except ZeroDivisionError:
            return ToolResult(self.name, False, "division by zero")
        except Exception as e:
            return ToolResult(self.name, False, f"could not evaluate: {e}")


class GetTimeTool(NexaTool):
    name = "get_time"
    description = "Return the current date and time. Optionally accept an IANA timezone."
    parameters = {
        "timezone": ToolParameter("string", "Optional IANA timezone, e.g. 'Asia/Jakarta'.", required=False),
    }

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        tz = str(args.get("timezone", "UTC"))
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(tz))
            formatted = now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
            return ToolResult(
                self.name, True,
                f"{formatted}\n(iso: {now.isoformat()})\n(zone: {tz})",
            )
        except Exception as e:
            return ToolResult(self.name, False, f"invalid timezone '{tz}': {e}")


class GenerateUuidTool(NexaTool):
    name = "generate_uuid"
    description = "Generate a random UUID v4 string."
    parameters = {}

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult(self.name, True, str(uuid.uuid4()))
