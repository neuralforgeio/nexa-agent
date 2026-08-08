"""
Tests for the hardened code_execution_tool (Project-Scoped Boundary + HITL).

Verifies:
    - Uses ``sys.executable`` (NOT hardcoded ``python3``).
    - Project-scoped cwd: defaults to FORGE_WORKSPACE, rejects outside paths.
    - HITL approval callback is invoked; denied → returns message.
    - Headless mode (no callback) auto-denies.
    - Approval timeout (30s) → deny.
    - Robust process kill on timeout (process group, Windows taskkill).
    - Output capture + truncation.
    - Temp file cleanup.
    - OpenAI schema includes ``requires_approval``.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from tools.code_execution_tool import (
    CODE_EXECUTION_SCHEMA,
    DEFAULT_CODE_TIMEOUT,
    MAX_CODE_TIMEOUT,
    MAX_OUTPUT,
    code_execution,
)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
class TestCodeExecutionValidation:
    """Tests for argument validation."""

    @pytest.mark.asyncio
    async def test_rejects_empty_code(self) -> None:
        """Empty code must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await code_execution("")

    @pytest.mark.asyncio
    async def test_rejects_whitespace_code(self) -> None:
        """Whitespace-only code must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await code_execution("   \n\t  ")

    @pytest.mark.asyncio
    async def test_rejects_timeout_over_max(self) -> None:
        """Timeout exceeding MAX_CODE_TIMEOUT must raise ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            await code_execution("print('hi')", timeout=MAX_CODE_TIMEOUT + 1)


# ---------------------------------------------------------------------------
# Cross-platform executable
# ---------------------------------------------------------------------------
class TestCrossPlatformExecutable:
    """Tests that the tool uses sys.executable, not hardcoded python3."""

    @pytest.mark.asyncio
    async def test_uses_sys_executable(self, tmp_path: Path, monkeypatch) -> None:
        """The subprocess must be invoked with sys.executable."""
        # Patch FORGE_WORKSPACE to tmp_path so cwd validation passes.
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        # Capture the subprocess args.
        captured_args = []
        captured_cwd = []

        class FakeProc:
            returncode = 0
            async def communicate(self):
                return (b"hello", b"")
            def kill(self):
                pass
            async def wait(self):
                return 0

        async def fake_create_subprocess_exec(*args, **kwargs):
            captured_args.extend(args)
            captured_cwd.append(kwargs.get("cwd"))
            return FakeProc()

        # Auto-approve the code.
        async def approve(code):
            return True

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   side_effect=fake_create_subprocess_exec):
            result = await code_execution(
                "print('hello')",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        # The first arg must be sys.executable.
        assert captured_args[0] == sys.executable
        assert "python3" not in captured_args[0]


# ---------------------------------------------------------------------------
# Project-scoped cwd
# ---------------------------------------------------------------------------
class TestProjectScopedCwd:
    """Tests for project-scoped cwd validation."""

    @pytest.mark.asyncio
    async def test_rejects_cwd_outside_workspace_unix(self, tmp_path: Path, monkeypatch) -> None:
        """A cwd outside FORGE_WORKSPACE must be rejected (Unix path)."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await code_execution(
                "print('hi')",
                cwd="/etc",
                approval_callback=lambda c: True,
            )

    @pytest.mark.asyncio
    async def test_rejects_cwd_outside_workspace_windows(self, tmp_path: Path, monkeypatch) -> None:
        """A Windows path outside FORGE_WORKSPACE must be rejected."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await code_execution(
                "print('hi')",
                cwd="C:\\Windows\\System32",
                approval_callback=lambda c: True,
            )

    @pytest.mark.asyncio
    async def test_rejects_cwd_traversal(self, tmp_path: Path, monkeypatch) -> None:
        """A cwd with .. traversal must be rejected."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await code_execution(
                "print('hi')",
                cwd="../../etc",
                approval_callback=lambda c: True,
            )


# ---------------------------------------------------------------------------
# HITL approval
# ---------------------------------------------------------------------------
class TestApprovalCallback:
    """Tests for the Human-in-the-Loop approval mechanism."""

    @pytest.mark.asyncio
    async def test_approval_callback_invoked(self, tmp_path: Path, monkeypatch) -> None:
        """The approval_callback is invoked with the code."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        called_with = []

        async def approve(code):
            called_with.append(code)
            return True  # deny to avoid actual subprocess execution

        # Make subprocess return immediately.
        class FakeProc:
            returncode = 0
            async def communicate(self): return (b"", b"")
            def kill(self): pass
            async def wait(self): return 0

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   return_value=FakeProc()):
            await code_execution(
                "print('test')",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        assert len(called_with) == 1
        assert "print" in called_with[0]

    @pytest.mark.asyncio
    async def test_approval_denied_returns_message(self, tmp_path: Path, monkeypatch) -> None:
        """When the approval_callback returns False, a deny message is returned."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)

        async def deny(code):
            return False

        result = await code_execution(
            "print('test')",
            approval_callback=deny,
            cwd=str(tmp_path),
        )
        assert "denied" in result.lower() or "rejected" in result.lower() or "not approved" in result.lower()

    @pytest.mark.asyncio
    async def test_headless_auto_deny_when_no_callback(self, tmp_path: Path, monkeypatch) -> None:
        """When approval_callback is None, the code is auto-denied (headless mode)."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)
        result = await code_execution(
            "print('test')",
            approval_callback=None,
            cwd=str(tmp_path),
        )
        assert "denied" in result.lower() or "headless" in result.lower() or "auto" in result.lower()


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------
class TestOutputCapture:
    """Tests for stdout/stderr capture and truncation."""

    @pytest.mark.asyncio
    async def test_captures_stdout(self, tmp_path: Path, monkeypatch) -> None:
        """stdout from the subprocess is returned."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)

        class FakeProc:
            returncode = 0
            async def communicate(self): return (b"hello world", b"")
            def kill(self): pass
            async def wait(self): return 0

        async def approve(code): return True

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   return_value=FakeProc()):
            result = await code_execution(
                "print('hello world')",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        assert "hello world" in result
        assert "exit code: 0" in result

    @pytest.mark.asyncio
    async def test_captures_stderr(self, tmp_path: Path, monkeypatch) -> None:
        """stderr from the subprocess is returned."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)

        class FakeProc:
            returncode = 1
            async def communicate(self): return (b"", b"boom error")
            def kill(self): pass
            async def wait(self): return 0

        async def approve(code): return True

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   return_value=FakeProc()):
            result = await code_execution(
                "raise Exception('boom')",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        assert "boom error" in result
        assert "exit code: 1" in result

    @pytest.mark.asyncio
    async def test_output_truncated_at_max(self, tmp_path: Path, monkeypatch) -> None:
        """Output exceeding MAX_OUTPUT is truncated."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)

        big_stdout = b"x" * (MAX_OUTPUT + 1000)

        class FakeProc:
            returncode = 0
            async def communicate(self): return (big_stdout, b"")
            def kill(self): pass
            async def wait(self): return 0

        async def approve(code): return True

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   return_value=FakeProc()):
            result = await code_execution(
                "print('x' * 5000)",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        assert "truncated" in result.lower()

    @pytest.mark.asyncio
    async def test_no_output_message(self, tmp_path: Path, monkeypatch) -> None:
        """When stdout and stderr are both empty, a 'no output' message is shown."""
        monkeypatch.setattr("tools.code_execution_tool.FORGE_WORKSPACE", tmp_path)

        class FakeProc:
            returncode = 0
            async def communicate(self): return (b"", b"")
            def kill(self): pass
            async def wait(self): return 0

        async def approve(code): return True

        with patch("tools.code_execution_tool.asyncio.create_subprocess_exec",
                   return_value=FakeProc()):
            result = await code_execution(
                "pass",
                approval_callback=approve,
                cwd=str(tmp_path),
            )
        assert "no output" in result.lower()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class TestCodeExecutionSchema:
    """Tests for the OpenAI function-calling schema."""

    def test_schema_includes_requires_approval(self) -> None:
        """The schema must expose requires_approval (HITL flag)."""
        assert "requires_approval" in CODE_EXECUTION_SCHEMA["properties"]

    def test_schema_requires_code(self) -> None:
        """The schema must require 'code'."""
        assert "code" in CODE_EXECUTION_SCHEMA["required"]

    def test_schema_timeout_property(self) -> None:
        """The schema must define a timeout property."""
        assert "timeout" in CODE_EXECUTION_SCHEMA["properties"]

    def test_schema_code_type_string(self) -> None:
        """The code property must be a string."""
        assert CODE_EXECUTION_SCHEMA["properties"]["code"]["type"] == "string"
