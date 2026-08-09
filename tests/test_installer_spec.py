"""Static structural tests for the OpenForge installer scripts.

These do NOT run the installer (which would touch ~/.openforge/ and the host
system). They verify the on-disk specification that the unified installers
target the correct layout and gate the critical behaviors users rely on.

Rewritten for the v5 unified installer (OpenForge): the old spinner/partial-flag
machinery was intentionally simplified into a smaller, auditable script.
"""

from __future__ import annotations

import re
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parent.parent / "scripts" / "install" / "install.sh"
INSTALL_PS1 = Path(__file__).resolve().parent.parent / "scripts" / "install" / "install.ps1"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestInstallShStructure:
    """Verify the POSIX installer's required OpenForge contract."""

    def test_install_sh_is_shell(self):
        src = _read(INSTALL_SH)
        assert src.startswith("#!")

    def test_install_sh_targets_unified_home(self):
        src = _read(INSTALL_SH)
        assert 'FORGE_HOME' in src
        assert ".openforge" in src
        assert 'FORGE_LIB' in src

    def test_install_sh_lock_integrity(self):
        src = _read(INSTALL_SH)
        assert "openforge.integrity" in src and "write_lock" in src

    def test_install_sh_readonly_core(self):
        src = _read(INSTALL_SH)
        assert "chmod" in src and "a-w" in src

    def test_install_sh_clones_repo_url(self):
        src = _read(INSTALL_SH)
        assert "neuralforgeio/openforge" in src

    def test_install_sh_frontend_deps(self):
        src = _read(INSTALL_SH)
        assert "openforge_web" in src and "npm install" in src
        assert "command -v npm" in src or "command -v node" in src

    def test_install_sh_user_level(self):
        src = _read(INSTALL_SH)
        assert ".local/bin" in src
        assert "sudo" not in src.lower()

    def test_install_sh_mentions_binary(self):
        src = _read(INSTALL_SH)
        assert "openforge" in src


class TestInstallPs1Structure:
    """Verify the Windows installer's required OpenForge contract."""

    def test_install_ps1_banner(self):
        src = _read(INSTALL_PS1)
        assert "OpenForge" in src

    def test_install_ps1_targets_unified_home(self):
        src = _read(INSTALL_PS1)
        assert ".openforge" in src and "ForgeLib" in src

    def test_install_ps1_readonly_flag(self):
        src = _read(INSTALL_PS1)
        assert "IsReadOnly" in src or "chmod" in src

    def test_install_ps1_lock_integrity(self):
        src = _read(INSTALL_PS1)
        assert "openforge.integrity" in src and "write_lock" in src

    def test_install_ps1_clones_repo_url(self):
        src = _read(INSTALL_PS1)
        assert "neuralforgeio/openforge" in src

    def test_install_ps1_frontend_deps(self):
        src = _read(INSTALL_PS1)
        assert "openforge_web" in src and "npm install" in src

    def test_install_ps1_registers_path(self):
        src = _read(INSTALL_PS1)
        assert "Environment]::SetEnvironmentVariable" in src

    def test_install_ps1_next_steps(self):
        src = _read(INSTALL_PS1)
        assert "openforge --version" in src
        assert "openforge setup" in src
        assert "openforge-chat" in src


class TestInstallParity:
    """Shared invariants between sh and ps1 (same logical steps)."""

    def test_both_reference_openforge(self):
        assert "OpenForge" in _read(INSTALL_SH)
        assert "OpenForge" in _read(INSTALL_PS1)

    def test_both_have_lock_step(self):
        assert "write_lock" in _read(INSTALL_SH)
        assert "write_lock" in _read(INSTALL_PS1)
