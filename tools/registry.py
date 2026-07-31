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
    # Register the delegate tool (sub-agent spawning).
    from .delegate_tool import delegate, DELEGATE_SCHEMA
    registry.register(
        name="delegate",
        fn=delegate,
        description=(
            "Spawn a sub-agent to handle a specific subtask in isolation. "
            "The sub-agent gets its own context and tool access, then "
            "returns a summary of its work. Use for breaking complex "
            "tasks into smaller focused pieces."
        ),
        parameters=DELEGATE_SCHEMA,
    )
    # Register background process management tools.
    from .terminal_tool import list_background_processes, kill_background_process
    registry.register(
        name="list_background_processes",
        fn=list_background_processes,
        description="List all background processes spawned by the agent.",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    registry.register(
        name="kill_background_process",
        fn=kill_background_process,
        description="Terminate a background process by its PID.",
        parameters={
            "type": "object",
            "properties": {
                "pid": {
                    "type": "string",
                    "description": "The process ID (e.g. 'bg-a1b2c3d4').",
                }
            },
            "required": ["pid"],
        },
    )
    # Register web search tool.
    from .web_search_tool import web_search, WEB_SEARCH_SCHEMA
    registry.register(
        name="web_search",
        fn=web_search,
        description=(
            "Search the web for a query. Returns formatted results with "
            "title, URL, and snippet. Uses DuckDuckGo (no API key needed)."
        ),
        parameters=WEB_SEARCH_SCHEMA,
    )
    # Register code execution tool.
    from .code_execution_tool import code_execution, CODE_EXECUTION_SCHEMA
    registry.register(
        name="code_execution",
        fn=code_execution,
        description=(
            "Execute a Python code snippet in a sandboxed subprocess. "
            "Returns stdout and stderr. 10-second timeout."
        ),
        parameters=CODE_EXECUTION_SCHEMA,
    )
    # Register file patch tool.
    from .file_patch_tool import file_patch, FILE_PATCH_SCHEMA, revert_file, REVERT_FILE_SCHEMA
    registry.register(
        name="file_patch",
        fn=file_patch,
        description=(
            "Apply a unified diff patch to a file in the workspace. "
            "Enables surgical modifications without rewriting the entire file."
        ),
        parameters=FILE_PATCH_SCHEMA,
    )
    # v3.1.0: register revert_file tool (rollback to previous backup version).
    registry.register(
        name="revert_file",
        fn=revert_file,
        description=(
            "Revert a file to a previous backup version (v3.1.0). "
            "Use after file_patch to undo a patch. Versions 1-5 are kept."
        ),
        parameters=REVERT_FILE_SCHEMA,
    )
    # Register deep_research tool (v3.2.0).
    from agent.deep_research import deep_research_tool, DEEP_RESEARCH_SCHEMA
    registry.register(
        name="deep_research",
        fn=deep_research_tool,
        description=(
            "Deep research on a topic: reformulate questions, search multiple "
            "sources, extract facts, cross-validate, and synthesize a "
            "comprehensive answer with citations. Use for complex questions "
            "that need multiple sources."
        ),
        parameters=DEEP_RESEARCH_SCHEMA,
    )
    # v3.2.0: register terminal_exec tool (programmatic terminal control).
    from tools.terminal_exec_tool import TerminalExecTool, TERMINAL_EXEC_SCHEMA
    registry.register(
        name="terminal_exec",
        fn=TerminalExecTool().execute,
        description=(
            "Execute a terminal command with optional session persistence. "
            "Use this to run shell commands (npm install, pytest, etc.) on "
            "behalf of the user. All commands still respect the workspace "
            "sandbox and ~/.nexa/ security boundary."
        ),
        parameters=TERMINAL_EXEC_SCHEMA,
    )
    # v4.0.0: register the 20 planning tools.
    register_planning_tools(registry)
    # v4.0.0: load user-written tools from ~/.nexa/tools/ so anything the
    # agent drafted via create_tool earlier becomes callable immediately.
    load_user_tools(registry)
    return registry


def register_planning_tools(registry: ToolRegistry) -> ToolRegistry:
    """
    Register all 20 v4.0 planning tools onto ``registry``.

    Each registration is defensive — a tool that fails to register (e.g.
    due to a name clash) is logged and skipped rather than crashing the
    agent.

    Args:
        registry: The registry to augment.

    Returns:
        The same registry (for chaining).
    """
    from tools.planning import PLANNING_TOOLS

    for name, fn, description, params in PLANNING_TOOLS:
        if registry.has(name):  # pragma: no cover - collision guard
            continue
        registry.register(name=name, fn=fn, description=description, parameters=params)
    return registry


def load_user_tools(registry: ToolRegistry) -> ToolRegistry:
    """
    Scan ``~/.nexa/tools/`` and register every user-drafted tool.

    Files in that directory are expected to expose:
      - an async function named after the file (``my_tool.py`` → ``my_tool``)
      - a module-level ``<NAME>_SCHEMA`` dict (OpenAI function-calling format)

    Malformed files are skipped silently — this must never crash the agent.
    Designed to pair with :func:`tools.planning.self_extend.create_tool`.
    """
    import importlib.util
    import sys
    from pathlib import Path

    import nexa.config as _config
    tools_dir = Path(_config.NEXA_HOME) / "tools"
    if not tools_dir.is_dir():
        return registry

    for py_file in sorted(tools_dir.glob("*.py")):
        mod_name = f"nexa_user_{py_file.stem}"
        tool_name = py_file.stem
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py_file)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            fn = getattr(mod, tool_name, None)
            schema = getattr(mod, f"{tool_name.upper()}_SCHEMA", None)
            if fn is None or schema is None or not callable(fn):
                continue
            if registry.has(tool_name):
                # Don't shadow a built-in tool — respect core tools.
                continue
            description = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else f"User tool: {tool_name}"
            registry.register(
                name=tool_name,
                fn=fn,
                description=description[:300],
                parameters=schema,
            )
        except Exception:
            # Malformed user tools must never crash the agent.
            continue
    return registry
