"""
Tests for the terminal security hardening (block ~/.nexa access).

Verifies:
    - `cat ~/.nexa/.env` is blocked (API key exfiltration vector closed).
    - `cat ~/.nexa/memory/MEMORY.md` is blocked.
    - `cat ~/.nexa/nexa.db` is blocked.
    - `echo "x" > ~/.nexa/.env` (write) is blocked.
    - `$HOME/.nexa` and `$NEXA_HOME` references are blocked.
    - Absolute paths that resolve to NEXA_HOME are blocked.
    - Legitimate commands inside NEXA_WORKSPACE are NOT blocked (no false positives).
    - `cat nexa-workspace/file.txt` is allowed.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.terminal_tool import run_terminal_command, is_protected_path_reference
from nexa.config import NEXA_HOME, NEXA_WORKSPACE


# ---------------------------------------------------------------------------
# is_protected_path_reference unit tests
# ---------------------------------------------------------------------------
class TestIsProtectedPathReference:
    """Unit tests for the protected-path reference detector."""

    def test_detects_tilde_nexa(self) -> None:
        """`~/.nexa/.env` is detected as protected."""
        assert is_protected_path_reference("cat ~/.nexa/.env") is True

    def test_detects_dot_nexa_relative(self) -> None:
        """`cat .nexa/.env` (relative to home) is detected as protected."""
        # This is tricky — `.nexa` only resolves to ~/.nexa if cwd is home.
        # We err on the side of caution and block any reference to `.nexa/.env`.
        assert is_protected_path_reference("cat .nexa/.env") is True

    def test_detects_dollar_home_nexa(self) -> None:
        """`$HOME/.nexa` is detected as protected."""
        assert is_protected_path_reference("cat $HOME/.nexa/.env") is True

    def test_detects_dollar_nexa_home_env(self) -> None:
        """`$NEXA_HOME` is detected as protected."""
        assert is_protected_path_reference("cat $NEXA_HOME/.env") is True

    def test_detects_absolute_nexa_home_path(self, tmp_path: Path, monkeypatch) -> None:
        """An absolute path that resolves to NEXA_HOME is detected as protected."""
        # Use the resolved tmp_path (avoid Windows 8.3 short-path mismatch).
        fake_home = tmp_path.resolve() / "fakehome"
        fake_home.mkdir()
        (fake_home / ".env").write_text("test")
        # Patch nexa.config.NEXA_HOME to the resolved fake_home.
        monkeypatch.setattr("nexa.config.NEXA_HOME", fake_home)
        abs_path = str(fake_home / ".env")
        assert is_protected_path_reference(f"cat {abs_path}") is True

    def test_detects_secrets_subpath(self) -> None:
        """`~/.nexa/secrets/providers.json` is detected as protected."""
        assert is_protected_path_reference("cat ~/.nexa/secrets/providers.json") is True

    def test_detects_memory_subpath(self) -> None:
        """`~/.nexa/memory/MEMORY.md` is detected as protected."""
        assert is_protected_path_reference("cat ~/.nexa/memory/MEMORY.md") is True

    def test_allows_workspace_path(self) -> None:
        """A path inside NEXA_WORKSPACE is NOT protected."""
        assert is_protected_path_reference("cat nexa-workspace/notes.txt") is False

    def test_allows_unrelated_command(self) -> None:
        """A plain command with no path references is NOT protected."""
        assert is_protected_path_reference("echo hello") is False

    def test_allows_ls_in_workspace(self) -> None:
        """`ls` without path is NOT protected."""
        assert is_protected_path_reference("ls -la") is False

    def test_detects_write_to_nexa_home(self) -> None:
        """Writing to ~/.nexa is detected as protected."""
        assert is_protected_path_reference('echo "x" > ~/.nexa/.env') is True

    def test_detects_pipe_to_nexa_home(self) -> None:
        """Piping to ~/.nexa is detected as protected."""
        assert is_protected_path_reference("echo x | tee ~/.nexa/.env") is True


# ---------------------------------------------------------------------------
# Integration tests (run_terminal_command blocks protected paths)
# ---------------------------------------------------------------------------
class TestRunTerminalCommandBlocksProtectedPaths:
    """Tests that run_terminal_command rejects commands targeting NEXA_HOME."""

    @pytest.mark.asyncio
    async def test_blocks_cat_env(self) -> None:
        """`cat ~/.nexa/.env` must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat ~/.nexa/.env")

    @pytest.mark.asyncio
    async def test_blocks_cat_memory_md(self) -> None:
        """`cat ~/.nexa/memory/MEMORY.md` must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat ~/.nexa/memory/MEMORY.md")

    @pytest.mark.asyncio
    async def test_blocks_cat_db(self) -> None:
        """`cat ~/.nexa/nexa.db` must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat ~/.nexa/nexa.db")

    @pytest.mark.asyncio
    async def test_blocks_write_to_env(self) -> None:
        """Writing to ~/.nexa/.env must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command('echo "OPENAI_API_KEY=sk-leak" > ~/.nexa/.env')

    @pytest.mark.asyncio
    async def test_blocks_dollar_home_reference(self) -> None:
        """`$HOME/.nexa` references must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat $HOME/.nexa/.env")

    @pytest.mark.asyncio
    async def test_blocks_dollar_nexa_home(self) -> None:
        """`$NEXA_HOME` references must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat $NEXA_HOME/.env")

    @pytest.mark.asyncio
    async def test_blocks_secrets_providers_json(self) -> None:
        """`~/.nexa/secrets/providers.json` must be rejected."""
        with pytest.raises(ValueError, match="protected|NEXA_HOME|blocked"):
            await run_terminal_command("cat ~/.nexa/secrets/providers.json")

    @pytest.mark.asyncio
    async def test_allows_workspace_echo(self, tmp_path: Path, monkeypatch) -> None:
        """A legitimate command in the workspace must NOT be blocked."""
        monkeypatch.setattr("tools.terminal_tool.NEXA_WORKSPACE", tmp_path)

        class FakeProc:
            returncode = 0
            async def communicate(self): return (b"hi", b"")
            def kill(self): pass
            async def wait(self): return 0

        with patch("tools.terminal_tool.asyncio.create_subprocess_shell",
                   return_value=FakeProc()):
            result = await run_terminal_command("echo hello")
        assert "exit code: 0" in result
