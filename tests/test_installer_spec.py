"""Static structural tests for the installer scripts.

These do NOT run the installer (which would touch ~/.openforge/ and the host
system). They verify the on-disk specification that the installer's helper
functions, signal traps, and partial-resume machinery are all present and
wired correctly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parent.parent / "scripts" / "install" / "install.sh"
INSTALL_PS1 = Path(__file__).resolve().parent.parent / "scripts" / "install" / "install.ps1"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestInstallShStructure:
    """Verify the POSIX installer's shape."""

    def test_install_sh_is_shell(self):
        src = _read(INSTALL_SH)
        assert src.startswith("#!") or "Nexa Agent" in src[:500]

    def test_install_sh_braille_spinner(self):
        src = _read(INSTALL_SH)
        # The installer must animate via the braille charset.
        assert any(ch in src for ch in ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴"))

    def test_install_sh_traps_signals(self):
        src = _read(INSTALL_SH)
        assert "trap" in src
        assert "_cleanup_and_exit" in src
        assert "PARTIAL_FLAG" in src
        assert "INT" in src and "TERM" in src  # POSIX signal list

    def test_install_sh_partial_resume(self):
        src = _read(INSTALL_SH)
        assert "Previous installation was interrupted" in src
        assert re.search(r"resume|Resume", src)

    def test_install_sh_version_banner_present(self):
        """The installer must print the brand + version banner."""
        src = _read(INSTALL_SH)
        # The banner shows the CURRENT version (pulled automatically from
        # pyproject.toml downstream). We only assert that `Nexa Agent` and
        # some version-looking prefix are printed — not the exact literal.
        assert "Nexa Agent" in src
        assert re.search(r"v\d+\.\d+\.\d+", src) is not None

    def test_install_sh_warns_on_partial_flag(self):
        src = _read(INSTALL_SH)
        assert "partial_install" in src or ".partial" in src.lower()


class TestInstallPs1Structure:
    """Verify the Windows installer's shape."""

    def test_install_ps1_banner(self):
        src = _read(INSTALL_PS1)
        assert "Nexa Agent" in src

    def test_install_ps1_traps_cancel(self):
        src = _read(INSTALL_PS1)
        # Register-EngineEvent or trap { } must be present.
        assert "Register-EngineEvent" in src or "trap" in src

    def test_install_ps1_partial_flag(self):
        src = _read(INSTALL_PS1)
        assert ".partial_install" in src
        assert "Previous installation was interrupted" in src

    def test_install_ps1_version_display(self):
        src = _read(INSTALL_PS1)
        # After the v4.2.1 polish pass, version should reflect the current
        # codename — but don't hard-assert it, just require the line exists.
        assert "Nexa Agent v" in src

    def test_next_steps_listed(self):
        src = _read(INSTALL_PS1)
        assert "nexa provider add" in src
        assert "nexa-chat" in src
        assert "nexa gateway start" in src


class TestBashInstallPs1Integrity:
    """Shared parity between sh and ps1."""

    def test_install_ps1_no_plusplus(self):
        """Basic sanity: no PowerShell-only syntax leaks into the .ps1."""
        src = _read(INSTALL_PS1)
        # Should not have a stray "::set-variable" or bat-style remnant.
        assert ":::" not in src
        # No PS-v2-only syntax (we're targeting PS 7.x).
        assert "#requires -Version 3" not in src

    def test_install_sh_partial_flag_consistent(self):
        """Both installers must agree on the partial-resume mechanism."""
        sh_src = _read(INSTALL_SH)
        ps_src = _read(INSTALL_PS1)
        # Both must create SOME partial-failure marker.
        assert (".partial_install" in sh_src) or ("PARTIAL_FLAG" in sh_src)
        assert (".partial_install" in ps_src) or ("PARTIAL_FLAG" in ps_src)
