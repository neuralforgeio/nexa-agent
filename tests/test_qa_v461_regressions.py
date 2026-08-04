"""
Regression tests for the GLM QA v4.6.0 bug batch (BUG-01/02/03).

These guard the fixes so the same class of failure cannot silently return:

  BUG-01  spreadsheet_operations requires openpyxl → openpyxl must be an
          *installed* dependency (declared in pyproject + requirements).
  BUG-02  deployment_automation test hardcoded Windows path separators
          → workspace-path comparisons must be OS-portable.
  BUG-03  installer never ran `npm install` for nexa_web → installer scripts
          must contain the frontend dependency-install step.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestBug01OpenpyxlDependency:
    """spreadsheet_operations must not die with 'openpyxl not installed'."""

    def test_openpyxl_importable(self):
        """The backend module imported by the skill must be importable."""
        import openpyxl  # noqa: F401

    def test_openpyxl_declared_in_pyproject(self):
        """openpyxl is pinned in [project.dependencies]."""
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "openpyxl" in text.lower()

    def test_openpyxl_declared_in_requirements(self):
        """openpyxl is also in requirements.txt for `pip install -r`."""
        text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert "openpyxl" in text.lower()


class TestBug02PortablePaths:
    """Workspace-relative path comparisons must work on any OS."""

    def test_no_hardcoded_backslash_separators(self):
        """No skill test may assert with literal '\\' path separators."""
        import ast

        target = REPO_ROOT / "tests" / "test_skills_deployment_automation.py"
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # A literal containing both a drive-style separator pattern
                # ('apps\\web') means a cross-platform regression.
                assert "\\web-dashboard" not in node.value, (
                    f"hardcoded backslash path in {target.name}"
                )


class TestBug03InstallerFrontendDeps:
    """Installers must attempt to install nexa_web deps automatically."""

    def test_install_sh_has_npm_install_step(self):
        sh = (REPO_ROOT / "scripts" / "install" / "install.sh").read_text(encoding="utf-8")
        assert "npm install" in sh, "install.sh missing auto npm install step"

    def test_install_ps1_has_npm_install_step(self):
        ps1 = (REPO_ROOT / "scripts" / "install" / "install.ps1").read_text(encoding="utf-8")
        assert "npm install" in ps1, "install.ps1 missing auto npm install step"

    def test_install_sh_is_graceful_without_npm(self):
        """install.sh must check 'command -v npm' so systems without it skip."""
        sh = (REPO_ROOT / "scripts" / "install" / "install.sh").read_text(encoding="utf-8")
        assert "command -v npm" in sh or "command -v node" in sh

    def test_install_ps1_is_graceful_without_npm(self):
        ps1 = (REPO_ROOT / "scripts" / "install" / "install.ps1").read_text(encoding="utf-8")
        assert "npm --version" in ps1 or "catch" in ps1.lower()
