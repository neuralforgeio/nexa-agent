"""
Nexa Agent — Tool Registry & Dispatcher
=======================================

This module defines :class:`ToolRegistry`, the central registry that owns
tool lifecycle. It provides:

- ``register(tool)``      — add a tool to the registry.
- ``get_openai_schemas()`` — return schemas in OpenAI function-calling format.
- ``execute(name, **kwargs)`` — dispatch a tool call by name.

Each tool is a callable with a ``name``, ``description``, and ``parameters``
schema. Tools must never raise — they return a :class:`ToolResult` with
``ok=False`` on failure.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import time
from typing import Any, Callable, Dict, List, Optional


class ToolResult:
    """
    The structured result of executing a tool.

    Attributes:
        tool:        The name of the tool that was executed.
        ok:          ``True`` if the tool succeeded, ``False`` otherwise.
        output:      The text output (or error message) from the tool.
        duration_ms: Wall-clock execution time in milliseconds.
    """

    def __init__(self, tool: str, ok: bool, output: str, duration_ms: int = 0) -> None:
        """Initialize a ToolResult."""
        self.tool = tool
        self.ok = ok
        self.output = output
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this result to a plain dict for JSON transport."""
        return {
            "tool": self.tool,
            "ok": self.ok,
            "output": self.output,
            "duration_ms": self.duration_ms,
        }


class ToolRegistry:
    """
    Central registry that owns tool discovery, schema generation, and dispatch.

    Usage::

        registry = ToolRegistry()
        registry.register("echo", echo_fn, schema={...})
        result = await registry.execute("echo", text="hello")
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        # Maps tool name -> (callable, schema dict).
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        fn: Callable,
        description: str,
        parameters: Dict[str, Any],
    ) -> "ToolRegistry":
        """
        Register a tool.

        Args:
            name:        The unique tool name (e.g. ``"read_file"``).
            fn:          The async callable that implements the tool.
            description: A human-readable description surfaced to the LLM.
            parameters:  A JSON-schema dict describing the tool's arguments.

        Returns:
            ``self`` to allow chaining.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = {
            "fn": fn,
            "description": description,
            "parameters": parameters,
        }
        return self

    def has(self, name: str) -> bool:
        """Return ``True`` if a tool with the given name is registered."""
        return name in self._tools

    def list_names(self) -> List[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """
        Return all tool schemas in OpenAI function-calling format.

        Each entry has the shape::

            {
                "type": "function",
                "function": {
                    "name": "...",
                    "description": "...",
                    "parameters": { "type": "object", "properties": {...}, "required": [...] }
                }
            }

        This can be passed directly to the ``tools`` parameter of the
        OpenAI chat-completions API.
        """
        schemas: List[Dict[str, Any]] = []
        for name, entry in self._tools.items():
            params = entry["parameters"] or {}
            properties = params.get("properties", {})
            required = params.get("required", [])
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": entry["description"],
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return schemas

    def describe(self) -> str:
        """
        Return a human-readable catalog of all tools for the system prompt.

        Each tool is listed as ``- name — description``.
        """
        lines = [
            f"- {name} — {entry['description']}"
            for name, entry in self._tools.items()
        ]
        return "\n".join(lines)

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """
        Execute a registered tool by name.

        This method never raises — if the tool is unknown or crashes, a
        :class:`ToolResult` with ``ok=False`` is returned.

        Args:
            name: The registered tool name.
            **kwargs: Arguments forwarded to the tool callable.

        Returns:
            A :class:`ToolResult` capturing the outcome and timing.
        """
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult(name, False, f"Unknown tool: {name}")
        start = time.time()
        try:
            output = await entry["fn"](**kwargs)
            ok = True
        except Exception as exc:  # noqa: BLE001 — tools must not crash the agent.
            output = f"Tool '{name}' crashed: {exc}"
            ok = False
        duration_ms = int((time.time() - start) * 1000)
        return ToolResult(name, ok, str(output), duration_ms)


def create_default_registry() -> ToolRegistry:
    """
    Create a :class:`ToolRegistry` pre-populated with the default Nexa tools.

    The default tool set includes:
    ``read_file``, ``write_file``, ``run_terminal_command``, ``generate_uuid``.

    Returns:
        A configured :class:`ToolRegistry` instance.
    """
    from .file_tools import read_file, write_file
    from .terminal_tool import generate_uuid, run_terminal_command

    registry = ToolRegistry()
    registry.register(
        name="read_file",
        fn=read_file,
        description=(
            "Read the contents of a text file inside the nexa workspace. "
            "Path is relative to the workspace root."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file, e.g. 'notes.txt'.",
                }
            },
            "required": ["path"],
        },
    )
    registry.register(
        name="write_file",
        fn=write_file,
        description=(
            "Write text content to a file inside the nexa workspace. "
            "Overwrites if the file exists, creates parent dirs if needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file.",
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write.",
                },
            },
            "required": ["path", "content"],
        },
    )
    registry.register(
        name="run_terminal_command",
        fn=run_terminal_command,
        description=(
            "Execute a shell command in the nexa workspace and return "
            "stdout/stderr. Output is capped at 2000 chars. 15s timeout."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                }
            },
            "required": ["command"],
        },
    )
    registry.register(
        name="generate_uuid",
        fn=generate_uuid,
        description="Generate a random UUID v4 string.",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    return registry
