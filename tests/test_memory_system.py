"""
Tests for the memory file system (MEMORY.md + USER.md).

Verifies:
    - Memory files are created at ~/.nexa/memory/.
    - append_to_memory and append_to_user add entries under correct sections.
    - read_memory_file and read_user_file return content.
    - build_memory_file_digest combines both files.
    - sync_db_to_files rebuilds the file from DB memories.
    - The memory curator writes to files when curating turns.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from agent.memory_files import (
    MEMORY_FILE,
    USER_FILE,
    append_to_memory,
    append_to_user,
    build_memory_file_digest,
    ensure_memory_dir,
    read_memory_file,
    read_user_file,
    sync_db_to_files,
    write_memory_file,
    write_user_file,
)
from agent.memory_curator import MemoryCurator
from nexa.state import ConversationDB


@pytest.fixture
def temp_memory_dir(tmp_path, monkeypatch):
    """Redirect memory files to a temp directory for isolation."""
    import agent.memory_files as mf

    temp_dir = tmp_path / "memory"
    temp_dir.mkdir()
    monkeypatch.setattr(mf, "MEMORY_DIR", temp_dir)
    monkeypatch.setattr(mf, "MEMORY_FILE", temp_dir / "MEMORY.md")
    monkeypatch.setattr(mf, "USER_FILE", temp_dir / "USER.md")
    return temp_dir


class TestMemoryFiles:
    """Tests for the file-based memory system."""

    def test_ensure_memory_dir_creates_directory(self, temp_memory_dir) -> None:
        """ensure_memory_dir must create the directory if it doesn't exist."""
        # The fixture already creates it, but verify it returns the path.
        result = ensure_memory_dir()
        assert result == temp_memory_dir

    def test_write_and_read_memory_file(self, temp_memory_dir) -> None:
        """write_memory_file then read_memory_file must round-trip."""
        content = "# Memory\n- Test entry"
        write_memory_file(content)
        assert read_memory_file() == content

    def test_write_and_read_user_file(self, temp_memory_dir) -> None:
        """write_user_file then read_user_file must round-trip."""
        content = "# User\n- Prefers Python"
        write_user_file(content)
        assert read_user_file() == content

    def test_read_nonexistent_memory_file(self, temp_memory_dir) -> None:
        """Reading a non-existent memory file must return empty string."""
        # Ensure file doesn't exist.
        if MEMORY_FILE.exists():
            MEMORY_FILE.unlink()
        assert read_memory_file() == ""

    def test_read_nonexistent_user_file(self, temp_memory_dir) -> None:
        """Reading a non-existent user file must return empty string."""
        if USER_FILE.exists():
            USER_FILE.unlink()
        assert read_user_file() == ""

    def test_append_to_memory_creates_section(self, temp_memory_dir) -> None:
        """append_to_memory must create a section if it doesn't exist."""
        append_to_memory("Test insight", kind="insight")
        content = read_memory_file()
        assert "## Insights" in content
        assert "Test insight" in content

    def test_append_to_memory_adds_to_existing_section(self, temp_memory_dir) -> None:
        """append_to_memory must add to an existing section."""
        append_to_memory("First insight", kind="insight")
        append_to_memory("Second insight", kind="insight")
        content = read_memory_file()
        assert "First insight" in content
        assert "Second insight" in content

    def test_append_to_user_creates_section(self, temp_memory_dir) -> None:
        """append_to_user must create a section if it doesn't exist."""
        append_to_user("Likes Python", kind="preference")
        content = read_user_file()
        assert "## Preferences" in content
        assert "Likes Python" in content

    def test_append_to_different_kinds(self, temp_memory_dir) -> None:
        """Appending different kinds must create separate sections."""
        append_to_memory("An insight", kind="insight")
        append_to_memory("A skill", kind="skill")
        content = read_memory_file()
        assert "## Insights" in content
        assert "## Skills" in content

    def test_build_memory_file_digest_empty(self, temp_memory_dir) -> None:
        """build_memory_file_digest must return empty string when no files exist."""
        assert build_memory_file_digest() == ""

    def test_build_memory_file_digest_with_content(self, temp_memory_dir) -> None:
        """build_memory_file_digest must combine both files."""
        write_memory_file("# Memory\n- Test insight")
        write_user_file("# User\n- Prefers Python")
        digest = build_memory_file_digest()
        assert "Agent Memory File" in digest
        assert "Test insight" in digest
        assert "User Profile" in digest
        assert "Prefers Python" in digest

    def test_sync_db_to_files(self, temp_memory_dir) -> None:
        """sync_db_to_files must rebuild MEMORY.md from DB memories."""
        memories = [
            {"kind": "insight", "content": "Test insight 1"},
            {"kind": "insight", "content": "Test insight 2"},
            {"kind": "preference", "content": "Prefers concise answers"},
            {"kind": "fact", "content": "User uses Python"},
            {"kind": "skill", "content": "Successfully used read_file"},
        ]
        sync_db_to_files(memories)
        content = read_memory_file()
        assert "## Insights" in content
        assert "Test insight 1" in content
        assert "Test insight 2" in content
        assert "## Preferences" in content
        assert "Prefers concise answers" in content
        assert "## Facts" in content
        assert "User uses Python" in content
        assert "## Skills" in content
        assert "Successfully used read_file" in content

    def test_sync_db_to_files_empty_list(self, temp_memory_dir) -> None:
        """sync_db_to_files with empty list must not write anything."""
        sync_db_to_files([])
        # File should not be created (or should remain unchanged).
        assert not MEMORY_FILE.exists() or read_memory_file() == ""


@pytest_asyncio.fixture
async def db_for_curator(tmp_path):
    """Provide a DB with temp NEXA_HOME for curator testing."""
    db = ConversationDB()
    await db.init()
    yield db


class TestMemoryCuratorFileIntegration:
    """Tests that the memory curator writes to files."""

    @pytest.mark.asyncio
    async def test_curate_turn_writes_to_files(self, db_for_curator, tmp_path, monkeypatch) -> None:
        """curate_turn must write memories to MEMORY.md and USER.md."""
        import agent.memory_files as mf

        temp_dir = tmp_path / "memory"
        temp_dir.mkdir()
        monkeypatch.setattr(mf, "MEMORY_DIR", temp_dir)
        monkeypatch.setattr(mf, "MEMORY_FILE", temp_dir / "MEMORY.md")
        monkeypatch.setattr(mf, "USER_FILE", temp_dir / "USER.md")

        # Use a unique phrase to avoid dedup from prior test runs.
        unique_phrase = "Remember that I prefer Python_uniquetest42"

        curator = MemoryCurator(db_for_curator)
        new_mems = await curator.curate_turn(
            unique_phrase,
            "Got it! I will remember that.",
            [],
        )
        assert len(new_mems) >= 1

        # The preference should be in USER.md.
        user_content = read_user_file()
        assert "Python_uniquetest42" in user_content

    @pytest.mark.asyncio
    async def test_build_memory_digest_includes_files(self, db_for_curator, tmp_path, monkeypatch) -> None:
        """build_memory_digest must include file-based memories."""
        import agent.memory_files as mf

        temp_dir = tmp_path / "memory"
        temp_dir.mkdir()
        monkeypatch.setattr(mf, "MEMORY_DIR", temp_dir)
        monkeypatch.setattr(mf, "MEMORY_FILE", temp_dir / "MEMORY.md")
        monkeypatch.setattr(mf, "USER_FILE", temp_dir / "USER.md")

        write_memory_file("# Memory\n- File-based insight")
        write_user_file("# User\n- File-based preference")

        curator = MemoryCurator(db_for_curator)
        digest = await curator.build_memory_digest()
        assert "File-based insight" in digest
        assert "File-based preference" in digest
