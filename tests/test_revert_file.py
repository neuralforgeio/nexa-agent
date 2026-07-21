"""
Tests for the File Patch rollback + revert_file (v3.1.0).

Verifies:
    - _rotate_backups creates .bak and shifts older versions.
    - revert_file restores a previous version.
    - revert_file raises on missing file / missing backup.
    - revert_file is registered as a tool.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path

import pytest

from tools._paths import resolve_in_workspace
from tools.file_patch_tool import (
    MAX_BACKUP_VERSIONS,
    REVERT_FILE_SCHEMA,
    _rotate_backups,
    file_patch,
    revert_file,
)
from tools.registry import create_default_registry


class TestRotateBackups:
    """Tests for the backup rotation helper."""

    def test_creates_bak_when_none_exists(self, tmp_path: Path, monkeypatch) -> None:
        """_rotate_backups creates a .bak when none exists."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        target = tmp_path / "file.txt"
        target.write_text("original")
        backup = _rotate_backups(target)
        assert backup is not None
        assert backup.exists()
        assert backup.read_text() == "original"

    def test_shifts_existing_bak_to_bak_1(self, tmp_path: Path, monkeypatch) -> None:
        """An existing .bak is shifted to .bak.1 when a new backup is made."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        target = tmp_path / "file.txt"
        target.write_text("v2")
        # Pre-create an existing .bak.
        (tmp_path / "file.txt.bak").write_text("v1")
        _rotate_backups(target)
        # The old .bak should now be .bak.1.
        assert (tmp_path / "file.txt.bak.1").exists()
        assert (tmp_path / "file.txt.bak.1").read_text() == "v1"
        # The new .bak should have the current content.
        assert (tmp_path / "file.txt.bak").read_text() == "v2"

    def test_returns_none_when_file_missing(self, tmp_path: Path, monkeypatch) -> None:
        """_rotate_backups returns None when the target doesn't exist."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        target = tmp_path / "nonexistent.txt"
        assert _rotate_backups(target) is None


class TestRevertFile:
    """Tests for the revert_file function."""

    @pytest.mark.asyncio
    async def test_revert_to_version_1(self, tmp_path: Path, monkeypatch) -> None:
        """revert_file restores the most recent .bak."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        monkeypatch.setattr("tools.file_patch_tool.NEXA_WORKSPACE", tmp_path)
        target = tmp_path / "file.txt"
        # Write v1, patch to v2 (creates .bak with v1).
        target.write_text("version 1")
        patch_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,1 @@\n-version 1\n+version 2\n"
        await file_patch("file.txt", patch_text)
        assert target.read_text().startswith("version 2")
        # Revert to v1.
        result = await revert_file("file.txt", version=1)
        assert "Reverted" in result
        assert target.read_text().startswith("version 1")

    @pytest.mark.asyncio
    async def test_revert_missing_file_raises(self, tmp_path: Path, monkeypatch) -> None:
        """revert_file raises ValueError for a missing file."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="file not found"):
            await revert_file("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_revert_missing_backup_raises(self, tmp_path: Path, monkeypatch) -> None:
        """revert_file raises ValueError when no backup exists."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        target = tmp_path / "file.txt"
        target.write_text("only version")
        with pytest.raises(ValueError, match="backup version.*not found"):
            await revert_file("file.txt", version=1)

    @pytest.mark.asyncio
    async def test_revert_directory_raises(self, tmp_path: Path, monkeypatch) -> None:
        """revert_file raises ValueError for a directory."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        (tmp_path / "subdir").mkdir()
        with pytest.raises(ValueError, match="directory"):
            await revert_file("subdir")

    @pytest.mark.asyncio
    async def test_revert_empty_path_raises(self, tmp_path: Path, monkeypatch) -> None:
        """revert_file raises ValueError for an empty path."""
        monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
        with pytest.raises(ValueError, match="path is required"):
            await revert_file("")


class TestRevertFileSchema:
    """Tests for the REVERT_FILE_SCHEMA."""

    def test_schema_has_path_property(self) -> None:
        """The schema must define a 'path' property."""
        assert "path" in REVERT_FILE_SCHEMA["properties"]

    def test_schema_has_version_property(self) -> None:
        """The schema must define a 'version' integer property."""
        assert "version" in REVERT_FILE_SCHEMA["properties"]
        assert REVERT_FILE_SCHEMA["properties"]["version"]["type"] == "integer"

    def test_schema_version_default_is_1(self) -> None:
        """The default version is 1."""
        assert REVERT_FILE_SCHEMA["properties"]["version"]["default"] == 1

    def test_schema_version_max_is_5(self) -> None:
        """The max version is 5 (MAX_BACKUP_VERSIONS)."""
        assert REVERT_FILE_SCHEMA["properties"]["version"]["maximum"] == MAX_BACKUP_VERSIONS

    def test_schema_required_includes_path(self) -> None:
        """'path' is required."""
        assert "path" in REVERT_FILE_SCHEMA["required"]


class TestRevertFileRegistered:
    """Tests that revert_file is registered as a tool."""

    def test_revert_file_registered(self) -> None:
        """The default registry must include revert_file."""
        reg = create_default_registry()
        names = set(reg.list_names())
        assert "revert_file" in names

    def test_revert_file_has_openai_schema(self) -> None:
        """revert_file must have an OpenAI function-calling schema."""
        reg = create_default_registry()
        schemas = reg.get_openai_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "revert_file" in names
