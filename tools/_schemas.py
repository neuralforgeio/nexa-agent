"""
OpenForge — Pydantic Schemas for Tools
=======================================

Defines a :class:`pydantic.BaseModel` for every tool's arguments. The
OpenAI function-calling JSON schema is then derived from these models,
eliminating the drift between the hand-written schema dicts and the
tool function signatures.

Why Pydantic?
    - **Single source of truth**: the model *is* the validation rule.
    - **Drift-free JSON schema**: ``model.model_json_schema()`` generates
      the OpenAI-compatible schema automatically.
    - **Clear errors**: ``ValidationError`` tells the caller exactly which
      field is wrong and why.
    - **Consistent with the FastAPI layer**: the HTTP server already uses
      Pydantic; now the tools do too.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Reusable constants (kept in sync with the tool modules)
# ---------------------------------------------------------------------------
MAX_TIMEOUT_SECONDS: float = 60.0
DEFAULT_TIMEOUT_SECONDS: float = 15.0
MAX_CODE_TIMEOUT_SECONDS: float = 30.0
MAX_DELEGATE_ITERATIONS: int = 8
DEFAULT_DELEGATE_ITERATIONS: int = 3
MAX_WEB_RESULTS: int = 10


def _no_traversal(value: str) -> str:
    """Reject paths that try to escape via ``..``.

    v5.2.0: absolute paths are permitted ONLY when the caller opts in via
    ``allow_absolute=True`` (used by the CLI/TUI after an explicit user grant).
    Default remains workspace-scoped for safety.
    """
    if not value or not value.strip():
        raise ValueError("path is required")
    if ".." in value.split("/"):
        raise ValueError("path traversal via '..' is not allowed")
    return value


class FileArgs(BaseModel):
    """Common fields for file tools (allow_absolute opt-in for out-of-workspace I/O)."""

    model_config = ConfigDict(extra="forbid")

    allow_absolute: bool = Field(
        False,
        description=(
            "If true, permit absolute paths outside the workspace (requires "
            "explicit approval from the user in the CLI/TUI)."
        ),
    )


# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------
class ReadFileArgs(FileArgs):
    """Arguments for the ``read_file`` tool."""

    path: str = Field(..., description="Path to the file (workspace-relative by default; absolute allowed when allow_absolute=True).")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        return _no_traversal(v)

    @model_validator(mode="after")
    def _require_workspace_scope(self):
        if getattr(self, "allow_absolute", False) is True:
            return self
        p = self.path
        if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
            raise ValueError("absolute paths are not allowed without allow_absolute=True")
        return self


class WriteFileArgs(FileArgs):
    """Arguments for the ``write_file`` tool."""

    path: str = Field(..., description="Path to the file (workspace-relative by default; absolute allowed when allow_absolute=True).")
    content: str = Field(..., description="The text content to write (max 1MB).")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        return _no_traversal(v)

    @model_validator(mode="after")
    def _require_workspace_scope(self):
        if getattr(self, "allow_absolute", False) is True:
            return self
        p = self.path
        if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
            raise ValueError("absolute paths are not allowed without allow_absolute=True")
        return self


# ---------------------------------------------------------------------------
# Terminal tools
# ---------------------------------------------------------------------------
class RunTerminalCommandArgs(BaseModel):
    """Arguments for the ``run_terminal_command`` tool."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., description="The shell command to execute.")
    timeout: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        description=f"Max execution time in seconds (default: {DEFAULT_TIMEOUT_SECONDS}, max: {MAX_TIMEOUT_SECONDS}).",
        gt=0,
        le=MAX_TIMEOUT_SECONDS,
    )
    cwd: Optional[str] = Field(
        default=None,
        description="Working directory inside the workspace (optional).",
    )
    env: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional environment variables to merge with os.environ.",
    )
    background: bool = Field(
        default=False,
        description="If true, run in the background and return a PID immediately.",
    )

    @field_validator("command")
    @classmethod
    def _validate_command(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("command must not be empty")
        return v


class GenerateUuidArgs(BaseModel):
    """Arguments for the ``generate_uuid`` tool (no parameters)."""

    model_config = ConfigDict(extra="forbid")


class ListBackgroundProcessesArgs(BaseModel):
    """Arguments for the ``list_background_processes`` tool (no parameters)."""

    model_config = ConfigDict(extra="forbid")


class KillBackgroundProcessArgs(BaseModel):
    """Arguments for the ``kill_background_process`` tool."""

    model_config = ConfigDict(extra="forbid")

    pid: str = Field(..., description="The Forge-assigned background process ID (e.g. 'bg-a1b2c3d4').")

    @field_validator("pid")
    @classmethod
    def _validate_pid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("pid is required")
        return v


# ---------------------------------------------------------------------------
# Delegate tool
# ---------------------------------------------------------------------------
class DelegateArgs(BaseModel):
    """Arguments for the ``delegate`` tool."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(..., description="The subtask to delegate to the sub-agent.")
    context: Optional[str] = Field(
        default=None, description="Optional additional context for the sub-agent."
    )
    max_iterations: int = Field(
        default=DEFAULT_DELEGATE_ITERATIONS,
        description=f"Max tool-call iterations for the sub-agent (default: {DEFAULT_DELEGATE_ITERATIONS}, max: {MAX_DELEGATE_ITERATIONS}).",
        ge=1,
        le=MAX_DELEGATE_ITERATIONS,
    )

    @field_validator("task")
    @classmethod
    def _validate_task(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task is required")
        return v


# ---------------------------------------------------------------------------
# Web search tool
# ---------------------------------------------------------------------------
class WebSearchArgs(BaseModel):
    """Arguments for the ``web_search`` tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="The search query.")
    num_results: int = Field(
        default=5,
        description="Number of results to return (default: 5, max: 10).",
        ge=1,
        le=MAX_WEB_RESULTS,
    )

    @field_validator("query")
    @classmethod
    def _validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query is required")
        return v


# ---------------------------------------------------------------------------
# Code execution tool
# ---------------------------------------------------------------------------
class CodeExecutionArgs(BaseModel):
    """Arguments for the ``code_execution`` tool."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="The Python code to execute.")
    timeout: float = Field(
        default=10.0,
        description=f"Max execution time in seconds (default: 10, max: {MAX_CODE_TIMEOUT_SECONDS}).",
        gt=0,
        le=MAX_CODE_TIMEOUT_SECONDS,
    )
    requires_approval: bool = Field(
        default=True,
        description="If true (default), the user is asked to approve the code before execution.",
    )
    cwd: Optional[str] = Field(
        default=None,
        description="Working directory inside the workspace (optional).",
    )

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("code is required")
        return v


# ---------------------------------------------------------------------------
# File patch tool
# ---------------------------------------------------------------------------
class FilePatchArgs(BaseModel):
    """Arguments for the ``file_patch`` tool."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Relative path to the file to patch.")
    patch: str = Field(..., description="The unified diff patch text.")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        return _no_traversal(v)

    @field_validator("patch")
    @classmethod
    def _validate_patch(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("patch is required")
        return v


# ---------------------------------------------------------------------------
# Registry: tool name → Pydantic model class
# ---------------------------------------------------------------------------
TOOL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "read_file": ReadFileArgs,
    "write_file": WriteFileArgs,
    "run_terminal_command": RunTerminalCommandArgs,
    "generate_uuid": GenerateUuidArgs,
    "delegate": DelegateArgs,
    "list_background_processes": ListBackgroundProcessesArgs,
    "kill_background_process": KillBackgroundProcessArgs,
    "web_search": WebSearchArgs,
    "code_execution": CodeExecutionArgs,
    "file_patch": FilePatchArgs,
}


def get_schema_for_tool(name: str) -> Optional[Type[BaseModel]]:
    """
    Return the Pydantic model class for ``name`` (case-insensitive).

    Args:
        name: The tool name (e.g. ``"read_file"``).

    Returns:
        The model class, or ``None`` if the tool is unknown.

    Example:
        >>> get_schema_for_tool("read_file") is ReadFileArgs
        True
        >>> get_schema_for_tool("nonexistent") is None
        True
    """
    return TOOL_SCHEMAS.get(name.lower())


def validate_tool_args(name: str, args: dict) -> BaseModel:
    """
    Validate ``args`` against the Pydantic model for tool ``name``.

    Args:
        name: The tool name.
        args: The arguments dict to validate.

    Returns:
        The validated :class:`BaseModel` instance.

    Raises:
        KeyError: If the tool is unknown.
        pydantic.ValidationError: If the arguments fail validation.

    Example:
        >>> model = validate_tool_args("read_file", {"path": "notes.txt"})
        >>> model.path
        'notes.txt'
    """
    model_cls = TOOL_SCHEMAS.get(name.lower())
    if model_cls is None:
        raise KeyError(f"no Pydantic schema registered for tool '{name}'")
    return model_cls(**args)
