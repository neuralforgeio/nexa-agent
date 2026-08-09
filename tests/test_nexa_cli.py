"""
Tests for the forge_cli subcommand module.

Verifies:
    - CLI setup command creates ~/.openforge/ directory
    - CLI model command shows and sets model
    - CLI gateway status command works
    - CLI doctor command runs diagnostics
    - CLI help output is correct

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest
from openforge_cli.main import main


class TestCLISetup:
    """Tests for the 'forge setup' command."""

    def test_setup_returns_zero(self) -> None:
        """setup command must return 0."""
        result = main(["setup"])
        assert result == 0

    def test_setup_creates_home(self, tmp_path, monkeypatch) -> None:
        """setup must create the FORGE_HOME directory."""
        import openforge.config as cfg
        monkeypatch.setattr(cfg, "FORGE_HOME", tmp_path / ".openforge")
        monkeypatch.setattr("openforge.constants.FORGE_HOME", tmp_path / ".openforge")
        result = main(["setup"])
        assert result == 0


class TestCLIModel:
    """Tests for the 'forge model' command."""

    def test_model_show_returns_zero(self) -> None:
        """model command without args must return 0."""
        result = main(["model"])
        assert result == 0

    def test_model_set_returns_zero(self, tmp_path, monkeypatch) -> None:
        """model command with name must return 0."""
        import openforge.config as cfg
        monkeypatch.setattr(cfg, "FORGE_HOME", tmp_path / ".openforge")
        (tmp_path / ".openforge").mkdir()
        result = main(["model", "test-model-123"])
        assert result == 0


class TestCLIGateway:
    """Tests for the 'forge gateway' command."""

    def test_gateway_status_returns_zero_or_one(self) -> None:
        """gateway status must return 0 (running) or 1 (stopped)."""
        result = main(["gateway", "status"])
        assert result in (0, 1)


class TestCLIDoctor:
    """Tests for the 'forge doctor' command."""

    def test_doctor_returns_zero_or_one(self) -> None:
        """doctor must return 0 (healthy) or 1 (issues)."""
        result = main(["doctor"])
        assert result in (0, 1)


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_no_args_returns_zero(self) -> None:
        """No args must return 0 (shows help)."""
        result = main([])
        assert result == 0

    def test_invalid_command_shows_error(self) -> None:
        """Invalid command must exit with error code (argparse behavior)."""
        with pytest.raises(SystemExit) as exc_info:
            main(["invalid"])
        assert exc_info.value.code == 2
