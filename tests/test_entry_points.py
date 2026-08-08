"""Tests for the entry-point wiring (pyproject.toml scripts).

After the OpenForge rename (Phase 2), the console scripts are:
    openforge          → openforge_cli.main:main
    openforge-chat     → src.cli:main
    openforge-agent    → src.run_agent:main
    openforge-gateway  → src.server:main
    openforge-tui      → ui_tui.app:main

The packages.find include list must contain openforge* and openforge_cli* so
they ship correctly.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _read_pyproject() -> str:
    """Read pyproject.toml as text."""
    return PYPROJECT.read_text(encoding="utf-8")


class TestEntryPoints:
    """Tests for [project.scripts]."""

    def test_openforge_points_to_openforge_cli_main(self) -> None:
        content = _read_pyproject()
        match = re.search(r'openforge\s*=\s*"([^"]+)"', content)
        assert match is not None, "openforge entry point not found"
        assert match.group(1) == "openforge_cli.main:main"

    def test_openforge_chat_points_to_src_cli(self) -> None:
        content = _read_pyproject()
        match = re.search(r'openforge[-_]chat\s*=\s*"([^"]+)"', content)
        assert match is not None, "openforge-chat not found"
        assert "src.cli" in match.group(1)

    def test_openforge_agent_points_to_src_run_agent(self) -> None:
        content = _read_pyproject()
        match = re.search(r'openforge[-_]agent\s*=\s*"([^"]+)"', content)
        assert match is not None, "openforge-agent not found"
        assert "src.run_agent" in match.group(1)

    def test_openforge_gateway_points_to_src_server(self) -> None:
        content = _read_pyproject()
        match = re.search(r'openforge[-_]gateway\s*=\s*"([^"]+)"', content)
        assert match is not None, "openforge-gateway not found"
        assert "src.server" in match.group(1)


class TestPackagesFind:
    """Tests for [tool.setuptools.packages.find] include list."""

    def test_include_contains_openforge(self) -> None:
        content = _read_pyproject()
        assert '"openforge*"' in content or "'openforge*'" in content

    def test_include_contains_openforge_cli(self) -> None:
        content = _read_pyproject()
        assert '"openforge_cli*"' in content or "'openforge_cli*'" in content

    def test_include_contains_ui_tui(self) -> None:
        content = _read_pyproject()
        assert '"ui_tui*"' in content or "'ui_tui*'" in content

    def test_include_contains_src(self) -> None:
        content = _read_pyproject()
        assert '"src*"' in content or "'src*'" in content
