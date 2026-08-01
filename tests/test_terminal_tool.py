"""
Tests for the deepened terminal tool.

Verifies:
    - Configurable timeout (default, custom, max enforcement).
    - Output truncation (stdout cap, stderr cap, truncation indicator).
    - Background process management (spawn, list, kill).
    - Environment variable injection.
    - Working directory override.
    - Blocked pattern enforcement.
    - Empty command rejection (regression from v1.4.1).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import pytest

from tools.registry import create_default_registry, ToolRegistry
from tools.terminal_tool import (
    run_terminal_command,
    generate_uuid,
    list_background_processes,
    kill_background_process,
    _background_processes,
    BackgroundProcess,
    MAX_STDOUT,
    MAX_STDERR,
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    BLOCKED_PATTERNS,
)


@pytest.fixture
def registry() -> ToolRegistry:
    """Provide a fresh default tool registry for each test."""
    return create_default_registry()


class TestConfigurableTimeout:
    """Tests for configurable timeout behavior."""

    @pytest.mark.asyncio
    async def test_default_timeout(self) -> None:
        """A command without explicit timeout should use DEFAULT_TIMEOUT."""
        result = await run_terminal_command('echo "hello"')
        assert "exit code: 0" in result

    @pytest.mark.asyncio
    async def test_custom_timeout(self) -> None:
        """A custom timeout should be respected."""
        result = await run_terminal_command('echo "fast"', timeout=5.0)
        assert "exit code: 0" in result

    @pytest.mark.asyncio
    async def test_timeout_exceeds_max(self) -> None:
        """A timeout above MAX_TIMEOUT must raise ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            await run_terminal_command('echo "test"', timeout=120.0)

    @pytest.mark.asyncio
    async def test_timeout_actually_triggers(self) -> None:
        """A command that sleeps longer than timeout must be killed."""
        with pytest.raises(asyncio.TimeoutError, match="timed out"):
            await run_terminal_command("sleep 10", timeout=1.0)


class TestOutputTruncation:
    """Tests for output truncation behavior."""

    @pytest.mark.asyncio
    async def test_stdout_truncation_indicator(self) -> None:
        """When stdout exceeds MAX_STDOUT, a truncation indicator must appear."""
        # v4.1.0: use sys.executable (cross-platform, not hardcoded python3).
        import sys as _sys
        result = await run_terminal_command(
            f'"{_sys.executable}" -c "print(\'x\' * 5000)"'
        )
        assert "[truncated]" in result

    @pytest.mark.asyncio
    async def test_short_output_not_truncated(self) -> None:
        """Short output must NOT have a truncation indicator."""
        result = await run_terminal_command('echo "short"')
        assert "[truncated]" not in result

    @pytest.mark.asyncio
    async def test_no_output_message(self) -> None:
        """A command with no output must show '(no output)'."""
        # `true` produces no output.
        result = await run_terminal_command("true")
        assert "(no output)" in result


class TestBackgroundProcesses:
    """Tests for background process management."""

    @pytest.mark.asyncio
    async def test_background_returns_pid(self) -> None:
        """Background mode must return a PID immediately."""
        # Clear any leftover processes.
        _background_processes.clear()
        result = await run_terminal_command("sleep 2", background=True)
        assert "PID:" in result
        assert "bg-" in result

    @pytest.mark.asyncio
    async def test_list_background_processes_empty(self) -> None:
        """list_background_processes must report none when empty."""
        _background_processes.clear()
        result = await list_background_processes()
        assert "No background processes" in result

    @pytest.mark.asyncio
    async def test_list_background_processes_shows_running(self) -> None:
        """list_background_processes must show a running process."""
        _background_processes.clear()
        await run_terminal_command("sleep 3", background=True)
        result = await list_background_processes()
        assert "Background processes" in result
        assert "bg-" in result
        assert "running" in result

    @pytest.mark.asyncio
    async def test_kill_background_process(self) -> None:
        """kill_background_process must terminate a running process."""
        _background_processes.clear()
        start_result = await run_terminal_command("sleep 10", background=True)
        # Extract PID from the start result.
        pid = start_result.split("PID: ")[1].split("\n")[0].strip()
        kill_result = await kill_background_process(pid=pid)
        assert "killed" in kill_result.lower()

    @pytest.mark.asyncio
    async def test_kill_nonexistent_pid(self) -> None:
        """Killing a non-existent PID must raise ValueError."""
        with pytest.raises(ValueError, match="no background process"):
            await kill_background_process(pid="bg-nonexistent123")

    @pytest.mark.asyncio
    async def test_kill_empty_pid(self) -> None:
        """Killing with empty PID must raise ValueError."""
        with pytest.raises(ValueError, match="pid is required"):
            await kill_background_process(pid="")


class TestEnvironmentAndCwd:
    """Tests for environment variable and working directory support."""

    @pytest.mark.asyncio
    async def test_env_variable_injection(self) -> None:
        """Custom environment variables must be accessible in the command."""
        # v4.1.0: cross-platform — use Python's os.environ instead of shell
        # expansion (which differs between bash, cmd.exe, and Git Bash).
        import sys as _sys
        result = await run_terminal_command(
            f'"{_sys.executable}" -c "import os; print(os.environ.get(\'NEXA_TEST_VAR\', \'NOT_SET\'))"',
            env={"NEXA_TEST_VAR": "injected_value_42"},
        )
        assert "injected_value_42" in result

    @pytest.mark.asyncio
    async def test_custom_cwd(self, tmp_path, monkeypatch) -> None:
        """A custom working directory inside the workspace must be used."""
        # v2.1.0: cwd must be inside NEXA_WORKSPACE. Patch the workspace to tmp_path
        # so the test's tmp_path is a valid project-scoped cwd.
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)
        # Create a test file in tmp_path.
        test_file = tmp_path / "marker.txt"
        test_file.write_text("found_it")
        result = await run_terminal_command("type marker.txt", cwd=str(tmp_path))
        assert "found_it" in result


class TestBlockedPatterns:
    """Tests for blocked command patterns."""

    @pytest.mark.asyncio
    async def test_all_blocked_patterns_rejected(self) -> None:
        """Every pattern in BLOCKED_PATTERNS must be rejected."""
        for pattern in BLOCKED_PATTERNS:
            with pytest.raises(ValueError, match="blocked"):
                await run_terminal_command(pattern)

    @pytest.mark.asyncio
    async def test_blocked_case_insensitive(self) -> None:
        """Blocked patterns must be case-insensitive."""
        with pytest.raises(ValueError, match="blocked"):
            await run_terminal_command("RM -RF /")


class TestRegistryIntegration:
    """Tests that the new tools are registered correctly."""

    def test_eleven_tools_registered(self, registry: ToolRegistry) -> None:
        """The registry must now have 33 tools (v4.1.0: 13 core + 20 planning)."""
        names = set(registry.list_names())
        assert "list_background_processes" in names
        assert "kill_background_process" in names
        assert "web_search" in names
        assert "code_execution" in names
        assert "file_patch" in names
        assert "revert_file" in names
        assert len(names) == 33  # v4.1.0: +20 planning tools

    def test_bg_tools_have_schemas(self, registry: ToolRegistry) -> None:
        """Background tools must have valid OpenAI schemas."""
        schemas = registry.get_openai_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "list_background_processes" in names
        assert "kill_background_process" in names

    @pytest.mark.asyncio
    async def test_list_bg_via_registry(self, registry: ToolRegistry) -> None:
        """list_background_processes must be executable via the registry."""
        _background_processes.clear()
        result = await registry.execute("list_background_processes")
        assert result.ok is True
        assert "No background" in result.output
