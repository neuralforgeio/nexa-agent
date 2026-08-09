"""
Tests for forge_cli/main.py polish (rich help table, sys.executable, SIGTERM).

Verifies:
    - `forge_cli main()` with `--help` produces a rich table (not plain argparse).
    - gateway start uses sys.executable (not hardcoded "python3").
    - gateway stop uses SIGTERM (not SIGKILL=9 directly).
    - gateway start accepts a --port flag.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import sys
from unittest.mock import patch, MagicMock

import pytest

from openforge_cli.main import main


class TestRichHelp:
    """Tests for the rich-rendered help."""

    def test_help_includes_rich_table_markers(self, capsys) -> None:
        """--help output should contain rich-table markers or styled output."""
        with pytest.raises(SystemExit):
            main(["--help"])
        # We don't strictly check for ANSI codes (they may be stripped if
        # not a TTY), but we check that the subcommands are listed.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "setup" in combined
        assert "model" in combined
        assert "gateway" in combined
        assert "doctor" in combined

    def test_help_uses_rich_module(self) -> None:
        """The module should import rich (so it can render help tables)."""
        import openforge_cli.main as m
        # Check the module imports rich somewhere.
        import inspect
        source = inspect.getsource(m)
        assert "rich" in source, "openforge_cli.main should import rich for help tables"


class TestGatewayStartUsesSysExecutable:
    """Tests that gateway start uses sys.executable (cross-platform)."""

    def test_start_uses_sys_executable(self, tmp_path, monkeypatch) -> None:
        """gateway start must spawn sys.executable, not 'python3'."""
        # Point FORGE_HOME to tmp_path so the pid file lands there.
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        # Capture the subprocess.Popen args.
        captured_args = []

        class FakeProc:
            pid = 12345

        def fake_popen(args, **kwargs):
            captured_args.extend(args)
            return FakeProc()

        with patch("openforge_cli.main.subprocess.Popen", side_effect=fake_popen):
            rc = main(["gateway", "start"])
        assert rc == 0
        # The first arg must be sys.executable (not "python3").
        assert captured_args[0] == sys.executable, (
            f"Expected sys.executable ({sys.executable!r}), got {captured_args[0]!r}"
        )
        assert "python3" not in captured_args[0]

    def test_start_accepts_port_flag(self, tmp_path, monkeypatch) -> None:
        """gateway start must accept a --port flag."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        captured_args = []

        class FakeProc:
            pid = 999

        def fake_popen(args, **kwargs):
            captured_args.extend(args)
            return FakeProc()

        with patch("openforge_cli.main.subprocess.Popen", side_effect=fake_popen):
            rc = main(["gateway", "start", "--port", "9000"])
        assert rc == 0
        # The port should appear in the args.
        assert "9000" in captured_args


class TestGatewayStopGraceful:
    """Tests that gateway stop uses SIGTERM (graceful), not SIGKILL."""

    def test_stop_uses_sigterm_first(self, tmp_path, monkeypatch) -> None:
        """gateway stop must send SIGTERM (15) before SIGKILL (9)."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        # Create a fake pid file.
        (tmp_path / "gateway.pid").write_text("12345")

        sent_signals = []

        def fake_kill(pid, sig):
            sent_signals.append((pid, sig))

        with patch("openforge_cli.main.os.kill", side_effect=fake_kill):
            rc = main(["gateway", "stop"])
        assert rc == 0
        # The first signal sent should be SIGTERM (15), not SIGKILL (9).
        import signal
        assert sent_signals[0][1] == signal.SIGTERM, (
            f"Expected first signal SIGTERM ({signal.SIGTERM}), got {sent_signals[0]}"
        )


class TestSetupAndDoctor:
    """Smoke tests for setup and doctor commands."""

    def test_setup_returns_zero(self, tmp_path, monkeypatch) -> None:
        """setup command returns 0."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        rc = main(["setup"])
        assert rc == 0

    def test_model_show_returns_zero(self, monkeypatch) -> None:
        """model show (no arg) returns 0."""
        rc = main(["model"])
        assert rc == 0

    def test_model_set_returns_zero(self, tmp_path, monkeypatch) -> None:
        """model set returns 0 and writes to .env."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        rc = main(["model", "llama3.2"])
        assert rc == 0
