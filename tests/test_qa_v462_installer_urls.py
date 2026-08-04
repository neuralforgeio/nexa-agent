"""
Regression test for GLM QA v4.6.x:
- BUG-04: installer URLs pointed at dead paths after the v4.3.0 reorg.
   README.md + installer scripts must reference the correct sub-path
   ``scripts/install/install.sh`` (not the legacy ``scripts/install.sh``).

This test purposely has NO temp files — it reads the live repo files.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


CORRECT_SH = "scripts/install/install.sh"
CORRECT_PS1 = "scripts/install/install.ps1"


class TestBug04InstallerUrls:
    """Every published installer command must resolve to a script that exists."""

    def test_readme_installer_sh_path_is_correct(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert CORRECT_SH in readme
        assert "raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh" not in readme

    def test_readme_installer_ps1_path_is_correct(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert CORRECT_PS1 in readme
        assert "raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1" not in readme

    def test_install_sh_self_reference(self):
        sh = (REPO_ROOT / CORRECT_SH).read_text(encoding="utf-8")
        assert CORRECT_SH in sh
        assert "raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh" not in sh

    def test_install_ps1_self_reference(self):
        ps1 = (REPO_ROOT / CORRECT_PS1).read_text(encoding="utf-8")
        assert CORRECT_PS1 in ps1
        assert "raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1" not in ps1

    def test_docs_plugin_icon_uses_correct_paths(self):
        doc = (REPO_ROOT / "docs" / "internal" / "README_PLUGIN_ICON.html").read_text(encoding="utf-8")
        assert CORRECT_SH in doc
        assert CORRECT_PS1 in doc
