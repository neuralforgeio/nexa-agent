"""Unit tests for openforge.path_resolver, path_protection, integrity."""
from pathlib import Path

import pytest

from openforge import integrity, path_protection, path_resolver


class TestPathResolver:
    def test_default_home(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FORGE_HOME", raising=False)
        monkeypatch.delenv("FORGE_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        home = path_resolver.get_forge_home()
        assert home == (tmp_path / ".openforge"), home

    def test_forge_home_env_wins(self, monkeypatch, tmp_path):
        custom = tmp_path / "custom-forge"
        custom.mkdir()
        monkeypatch.setenv("FORGE_HOME", str(custom))
        assert path_resolver.get_forge_home() == custom
        assert path_resolver.get_forge_lib() == custom / "lib"
        assert path_resolver.is_core_path(custom / "lib" / "x.py") is True
        assert path_resolver.is_core_path(tmp_path / "outside.py") is False

    def test_nexa_home_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FORGE_HOME", raising=False)
        monkeypatch.setenv("FORGE_HOME", str(tmp_path / "legacy"))
        assert path_resolver.get_forge_home() == tmp_path / "legacy"

    def test_workspace_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FORGE_HOME", raising=False)
        monkeypatch.delenv("FORGE_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert path_resolver.get_forge_workspace() == tmp_path / ".openforge" / "workspace"


class TestPathProtection:
    def test_write_inside_lib_is_rejected(self, monkeypatch, tmp_path):
        lib = tmp_path / ".openforge" / "lib"
        lib.mkdir(parents=True)
        monkeypatch.setenv("FORGE_HOME", str(tmp_path / ".openforge"))
        with pytest.raises(path_protection.ReadOnlyViolation):
            path_protection.ensure_safe_write(lib / "core.py", "write")

    def test_write_outside_lib_is_allowed(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FORGE_HOME", str(tmp_path / ".openforge"))
        # Should not raise
        path_protection.ensure_safe_write(tmp_path / "user_note.md", "write")

    def test_delete_inside_lib_is_rejected(self, monkeypatch, tmp_path):
        lib = tmp_path / ".openforge" / "lib" / "agent"
        lib.mkdir(parents=True)
        monkeypatch.setenv("FORGE_HOME", str(tmp_path / ".openforge"))
        with pytest.raises(path_protection.ReadOnlyViolation):
            path_protection.ensure_safe_write(lib / "agent", "delete")


def test_integrity_roundtrip(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "a.py").write_text("print('hello')\n")
    (lib / "b.txt").write_text("world\n")

    lock = integrity.write_lock(lib)
    assert lock.exists()
    ok, mismatch, missing, extra = integrity.verify(lib)
    assert ok, (mismatch, missing, extra)

    # tamper: modify an existing file
    (lib / "a.py").write_text("print('tampered')\n")
    ok, mismatch, missing, extra = integrity.verify(lib)
    assert not ok
    assert "a.py" in mismatch

    # missing: delete a tracked file
    (lib / "b.txt").unlink()
    ok, mismatch, missing, extra = integrity.verify(lib)
    assert not ok
    assert "b.txt" in missing

    # extra: add an untracked file
    (lib / "b.txt").write_text("world\n")
    (lib / "c_new.py").write_text("x = 1\n")
    ok, mismatch, missing, extra = integrity.verify(lib)
    assert not ok
    assert "c_new.py" in extra
