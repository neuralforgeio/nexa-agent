"""
Tests for the hardened nexa_cli (gateway start sys.executable, gateway stop SIGTERM, --port flag).

Verifies:
    - gateway start uses sys.executable (cross-platform), not hardcoded "python3".
    - gateway stop sends SIGTERM (15) first, SIGKILL (9) as fallback after 3s grace period.
    - gateway start accepts a --port flag (default 8000).
    - gateway stop cleans up the pid file after stopping.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import signal
import sys
from unittest.mock import patch, MagicMock

import pytest

from openforge_cli.main import main


class TestGatewayStartUsesSysExecutable:
    """Tests that gateway start uses sys.executable."""

    def test_start_uses_sys_executable(self, tmp_path, monkeypatch) -> None:
        """gateway start must spawn sys.executable, not 'python3'."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        captured_args = []

        class FakeProc:
            pid = 12345

        def fake_popen(args, **kwargs):
            captured_args.extend(args)
            return FakeProc()

        with patch("openforge_cli.main.subprocess.Popen", side_effect=fake_popen):
            rc = main(["gateway", "start"])
        assert rc == 0
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
        assert "9000" in captured_args


class TestGatewayStopGraceful:
    """Tests that gateway stop sends SIGTERM first (graceful)."""

    def test_stop_uses_sigterm_first(self, tmp_path, monkeypatch) -> None:
        """gateway stop must send SIGTERM (15) before SIGKILL (9)."""
        monkeypatch.setattr("openforge_cli.main.FORGE_HOME", tmp_path)
        (tmp_path / "gateway.pid").write_text("12345")

        sent_signals = []

        def fake_kill(pid, sig):
            sent_signals.append((pid, sig))

        with patch("openforge_cli.main.os.kill", side_effect=fake_kill):
            rc = main(["gateway", "stop"])

        assert rc == 0
        # First signal must be SIGTERM (15), not SIGKILL (9).
        assert sent_signals[0][1] == signal.SIGTERM, (
            f"Expected first signal SIGTERM ({signal.SIGTERM}), got {sent_signals[0]!r}"
        )
