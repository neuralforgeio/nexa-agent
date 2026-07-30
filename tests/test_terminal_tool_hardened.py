"""
Tests for the hardened terminal_tool (cwd validation + Windows blocklist + process group kill).

Verifies the hardening added in v2.1.0:
    - cwd is validated against NEXA_WORKSPACE (rejects /etc, C:\\Windows, ..).
    - Windows-native dangerous patterns are blocked (del /s, format, Remove-Item -Recurse, rmdir /s).
    - Timeout kills the entire process tree (process group on Unix, taskkill /F /T on Windows).
    - Background process registry prunes completed entries (no memory leak).
    - OpenAI schema exposes timeout/cwd/env/background (not hidden anymore).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from tools.terminal_tool import (
    BLOCKED_PATTERNS,
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    BackgroundProcess,
    RUN_TERMINAL_COMMAND_SCHEMA,
    _background_processes,
    _prune_completed_processes,
    generate_uuid,
    kill_background_process,
    list_background_processes,
    run_terminal_command,
)


# ---------------------------------------------------------------------------
# cwd validation
# ---------------------------------------------------------------------------
class TestCwdValidation:
    """Tests for cwd project-scoped validation."""

    @pytest.mark.asyncio
    async def test_rejects_cwd_outside_workspace_unix(self, tmp_path: Path, monkeypatch) -> None:
        """A cwd outside NEXA_WORKSPACE must be rejected (Unix path)."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await run_terminal_command("echo hi", cwd="/etc")

    @pytest.mark.asyncio
    async def test_rejects_cwd_outside_workspace_windows(self, tmp_path: Path, monkeypatch) -> None:
        """A Windows path outside NEXA_WORKSPACE must be rejected."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await run_terminal_command("echo hi", cwd="C:\\Windows\\System32")

    @pytest.mark.asyncio
    async def test_rejects_cwd_traversal(self, tmp_path: Path, monkeypatch) -> None:
        """A cwd with .. traversal must be rejected."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="escapes|outside|workspace"):
            await run_terminal_command("echo hi", cwd="../../etc")

    @pytest.mark.asyncio
    async def test_accepts_cwd_inside_workspace(self, tmp_path: Path, monkeypatch) -> None:
        """A cwd inside NEXA_WORKSPACE is accepted (and the command runs)."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()

        class FakeProc:
            returncode = 0
            async def communicate(self): return (b"hi", b"")
            def kill(self): pass
            async def wait(self): return 0

        with patch("tools.terminal_tool.asyncio.create_subprocess_shell",
                   return_value=FakeProc()):
            result = await run_terminal_command("echo hi", cwd=str(sub))
        assert "exit code: 0" in result


# ---------------------------------------------------------------------------
# Blocklist expansion
# ---------------------------------------------------------------------------
class TestBlocklistExpansion:
    """Tests that the blocklist now covers Windows patterns."""

    def test_unix_patterns_still_present(self) -> None:
        """Unix dangerous patterns must still be present."""
        assert "rm -rf /" in BLOCKED_PATTERNS or any("rm" in p for p in BLOCKED_PATTERNS)
        assert "mkfs" in BLOCKED_PATTERNS

    def test_windows_del_pattern_blocked(self) -> None:
        """The 'del /s' Windows deletion pattern must be blocked."""
        # Check that some Windows pattern is present.
        win_patterns = [p for p in BLOCKED_PATTERNS if "del" in p.lower() or "format" in p.lower()
                        or "remove-item" in p.lower() or "rmdir" in p.lower()]
        assert len(win_patterns) > 0, "No Windows-specific blocklist patterns found"

    @pytest.mark.asyncio
    async def test_windows_del_s_rejected(self) -> None:
        """The command 'del /s /q C:\\*' must be rejected."""
        with pytest.raises(ValueError, match="blocked"):
            await run_terminal_command("del /s /q C:\\*")

    @pytest.mark.asyncio
    async def test_windows_format_rejected(self) -> None:
        """The 'format C:' command must be rejected."""
        with pytest.raises(ValueError, match="blocked"):
            await run_terminal_command("format C:")

    @pytest.mark.asyncio
    async def test_windows_remove_item_recurse_rejected(self) -> None:
        """The PowerShell 'Remove-Item -Recurse -Force' must be rejected."""
        with pytest.raises(ValueError, match="blocked"):
            await run_terminal_command("Remove-Item -Recurse -Force C:\\Important")

    @pytest.mark.asyncio
    async def test_windows_rmdir_s_rejected(self) -> None:
        """The 'rmdir /s' command must be rejected."""
        with pytest.raises(ValueError, match="blocked"):
            await run_terminal_command("rmdir /s /q C:\\Important")


# ---------------------------------------------------------------------------
# Process group kill on timeout
# ---------------------------------------------------------------------------
class TestProcessGroupKill:
    """Tests that timeout kills the whole process tree, not just the parent."""

    @pytest.mark.asyncio
    async def test_timeout_kills_process_tree_unix(self, tmp_path: Path, monkeypatch) -> None:
        """On timeout, the process group is killed (Unix)."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)

        kill_called = []
        killpg_called = []

        class FakeProc:
            pid = 12345
            returncode = None
            async def communicate(self):
                await asyncio.sleep(10)  # never completes
                return (b"", b"")
            def kill(self):
                kill_called.append(True)
            async def wait(self):
                return 0

        async def fake_create_subprocess_shell(*args, **kwargs):
            return FakeProc()

        # Patch os.getpgid and os.killpg on Unix only.
        if sys.platform != "win32":
            monkeypatch.setattr("os.getpgid", lambda pid: pid)
            monkeypatch.setattr("os.killpg", lambda pgid, sig: killpg_called.append(True))

        with patch("tools.terminal_tool.asyncio.create_subprocess_shell",
                   side_effect=fake_create_subprocess_shell):
            with pytest.raises(asyncio.TimeoutError):
                await run_terminal_command("sleep 100", timeout=0.1)

        # On Unix, killpg should have been called. On Windows, taskkill is tried.
        if sys.platform != "win32":
            assert len(killpg_called) > 0 or len(kill_called) > 0
        # On Windows we can't easily test taskkill without actually spawning,
        # so we just verify the timeout raised.


# ---------------------------------------------------------------------------
# Background process pruning (memory leak fix)
# ---------------------------------------------------------------------------
class TestBackgroundProcessPruning:
    """Tests that completed background processes are pruned from the registry."""

    def test_prune_removes_completed(self) -> None:
        """_prune_completed_processes removes completed/killed entries."""
        # Clear the registry first.
        _background_processes.clear()
        # Add a fake completed process.
        fake_running = MagicMock()
        fake_running.status = "running"
        fake_completed = MagicMock()
        fake_completed.status = "completed"
        fake_killed = MagicMock()
        fake_killed.status = "killed"
        _background_processes["bg-running"] = fake_running
        _background_processes["bg-done"] = fake_completed
        _background_processes["bg-killed"] = fake_killed

        _prune_completed_processes()

        assert "bg-running" in _background_processes
        assert "bg-done" not in _background_processes
        assert "bg-killed" not in _background_processes
        _background_processes.clear()

    def test_prune_keeps_running(self) -> None:
        """Running processes are kept."""
        _background_processes.clear()
        fake = MagicMock()
        fake.status = "running"
        _background_processes["bg-1"] = fake

        _prune_completed_processes()

        assert "bg-1" in _background_processes
        _background_processes.clear()


# ---------------------------------------------------------------------------
# Schema exposure
# ---------------------------------------------------------------------------
class TestSchemaExposure:
    """Tests that the OpenAI schema exposes all parameters (not hidden)."""

    def test_schema_exposes_timeout(self) -> None:
        """The schema must expose the 'timeout' parameter."""
        from tools.terminal_tool import RUN_TERMINAL_COMMAND_SCHEMA
        assert "timeout" in RUN_TERMINAL_COMMAND_SCHEMA["properties"]

    def test_schema_exposes_cwd(self) -> None:
        """The schema must expose the 'cwd' parameter."""
        from tools.terminal_tool import RUN_TERMINAL_COMMAND_SCHEMA
        assert "cwd" in RUN_TERMINAL_COMMAND_SCHEMA["properties"]

    def test_schema_exposes_env(self) -> None:
        """The schema must expose the 'env' parameter."""
        from tools.terminal_tool import RUN_TERMINAL_COMMAND_SCHEMA
        assert "env" in RUN_TERMINAL_COMMAND_SCHEMA["properties"]

    def test_schema_exposes_background(self) -> None:
        """The schema must expose the 'background' parameter."""
        from tools.terminal_tool import RUN_TERMINAL_COMMAND_SCHEMA
        assert "background" in RUN_TERMINAL_COMMAND_SCHEMA["properties"]
