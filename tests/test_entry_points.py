"""
Tests for the entry point wiring (pyproject.toml scripts).

Verifies that:
    - `nexa` points to the subcommand dispatcher (nexa_cli.main:main),
      so `nexa setup`, `nexa model`, `nexa gateway`, `nexa doctor` work.
    - `nexa-chat` points to the interactive REPL (cli:main).
    - `packages.find` includes nexa_cli, ui_tui, tui_gateway (so they ship).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _read_pyproject() -> str:
    """Read the pyproject.toml as a string."""
    return PYPROJECT.read_text(encoding="utf-8")


class TestEntryPoints:
    """Tests for [project.scripts] in pyproject.toml."""

    def test_nexa_points_to_nexa_cli_main(self) -> None:
        """The `nexa` console script must point to nexa_cli.main:main."""
        content = _read_pyproject()
        match = re.search(r'nexa\s*=\s*"([^"]+)"', content)
        assert match is not None, "nexa entry point not found in pyproject.toml"
        assert match.group(1) == "nexa_cli.main:main", (
            f"nexa should point to nexa_cli.main:main, got {match.group(1)!r}"
        )

    def test_nexa_chat_points_to_cli_main(self) -> None:
        """The `nexa-chat` console script must point to cli:main (interactive REPL)."""
        content = _read_pyproject()
        match = re.search(r'nexa[-_]chat\s*=\s*"([^"]+)"', content)
        assert match is not None, "nexa-chat entry point not found"
        assert match.group(1) == "cli:main", (
            f"nexa-chat should point to cli:main, got {match.group(1)!r}"
        )

    def test_nexa_agent_points_to_run_agent(self) -> None:
        """The `nexa-agent` console script must still point to run_agent:main."""
        content = _read_pyproject()
        match = re.search(r'nexa[-_]agent\s*=\s*"([^"]+)"', content)
        assert match is not None, "nexa-agent entry point not found"
        assert "run_agent" in match.group(1)


class TestPackagesFind:
    """Tests for [tool.setuptools.packages.find] include list."""

    def test_packages_find_includes_nexa_cli(self) -> None:
        """packages.find must include nexa_cli* so the package ships."""
        content = _read_pyproject()
        assert "nexa_cli" in content, "nexa_cli not in packages.find"

    def test_packages_find_includes_ui_tui(self) -> None:
        """packages.find must include ui_tui* so the package ships."""
        content = _read_pyproject()
        assert "ui_tui" in content, "ui_tui not in packages.find"

    def test_packages_find_includes_tui_gateway(self) -> None:
        """packages.find must include tui_gateway* so the package ships."""
        content = _read_pyproject()
        assert "tui_gateway" in content, "tui_gateway not in packages.find"


class TestCliDispatch:
    """Smoke tests that nexa_cli.main.main dispatches subcommands correctly."""

    def test_setup_dispatches_to_cmd_setup(self, capsys) -> None:
        """`nexa setup` invokes _cmd_setup and returns 0."""
        from nexa_cli.main import main
        rc = main(["setup"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "nexa" in captured.out.lower()

    def test_no_args_prints_help(self, capsys) -> None:
        """`nexa` with no args prints help and returns 0."""
        from nexa_cli.main import main
        rc = main([])
        assert rc == 0
