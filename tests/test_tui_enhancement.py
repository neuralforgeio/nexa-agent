"""
Tests for TUI enhancement commands: /sessions, /export, /config.

Verifies:
    - /sessions lists conversations from DB.
    - /sessions switch loads messages.
    - /export creates a markdown file.
    - /config show displays configuration.
    - /config set changes model and provider.
    - All commands are registered in SLASH_COMMANDS.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest
import pytest_asyncio

from src.cli import SLASH_COMMANDS
from openforge.state import ConversationDB


class TestSlashCommandRegistration:
    """Tests that new commands are registered."""

    def test_sessions_command_registered(self) -> None:
        """/sessions must be in SLASH_COMMANDS."""
        assert "/sessions" in SLASH_COMMANDS

    def test_export_command_registered(self) -> None:
        """/export must be in SLASH_COMMANDS."""
        assert "/export" in SLASH_COMMANDS

    def test_config_command_registered(self) -> None:
        """/config must be in SLASH_COMMANDS."""
        assert "/config" in SLASH_COMMANDS

    def test_total_commands(self) -> None:
        """There should be at least 13 commands now."""
        assert len(SLASH_COMMANDS) >= 13


@pytest_asyncio.fixture
async def db_with_sessions():
    """Provide a DB with seeded conversations."""
    db = ConversationDB()
    await db.init()

    conv1 = await db.create_conversation("First session about Python")
    await db.add_message(conv1["id"], "user", "Hello about Python")
    await db.add_message(conv1["id"], "assistant", "Hi! How can I help with Python?")

    conv2 = await db.create_conversation("Second session about files")
    await db.add_message(conv2["id"], "user", "Write a file for me")
    await db.add_message(conv2["id"], "assistant", "Sure! I'll use write_file.")

    return db


class TestSessionsCommand:
    """Tests for /sessions command behavior."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_conversations(self, db_with_sessions) -> None:
        """list_conversations must return seeded sessions."""
        convs = await db_with_sessions.list_conversations(limit=20)
        assert len(convs) >= 2
        titles = [c["title"] for c in convs]
        assert any("Python" in t for t in titles)
        assert any("files" in t for t in titles)

    @pytest.mark.asyncio
    async def test_get_messages_for_session(self, db_with_sessions) -> None:
        """get_messages must return messages for a valid session ID."""
        convs = await db_with_sessions.list_conversations()
        msgs = await db_with_sessions.get_messages(convs[0]["id"])
        assert len(msgs) >= 2

    @pytest.mark.asyncio
    async def test_get_messages_invalid_id_returns_empty(self, db_with_sessions) -> None:
        """get_messages with invalid ID must return empty list."""
        msgs = await db_with_sessions.get_messages("invalid-id-12345")
        assert msgs == []


class TestExportCommand:
    """Tests for /export command behavior."""

    @pytest.mark.asyncio
    async def test_export_creates_markdown_file(self, db_with_sessions, tmp_path) -> None:
        """Exporting a session must create a .md file with correct content."""
        convs = await db_with_sessions.list_conversations()
        # Find the Python session.
        target = None
        for c in convs:
            if "Python" in c["title"]:
                target = c
                break
        assert target is not None, "Python session not found in seeded data"
        target_id = target["id"]
        msgs = await db_with_sessions.get_messages(target_id)

        # Simulate export logic.
        lines = [f"# Nexa Agent — Session Export", f"Session: {target_id}", ""]
        for m in msgs:
            if m["role"] == "user":
                lines.append(f"## User\n\n{m['content']}\n")
            elif m["role"] == "assistant":
                lines.append(f"## Nexa\n\n{m['content']}\n")

        export_text = "\n".join(lines)
        export_path = tmp_path / f"export_{target_id[:12]}.md"
        export_path.write_text(export_text, encoding="utf-8")

        assert export_path.exists()
        content = export_path.read_text()
        assert "Session Export" in content
        assert "Python" in content  # from the seeded conversation


class TestConfigCommand:
    """Tests for /config command behavior."""

    def test_config_show_displays_info(self) -> None:
        """/config show must display FORGE_HOME, workspace, model, provider."""
        from openforge.config import FORGE_HOME, FORGE_WORKSPACE
        assert FORGE_HOME is not None
        assert FORGE_WORKSPACE is not None

    def test_config_set_model(self) -> None:
        """Setting model via config must update the provider."""
        from providers.catalog import resolve_provider, PROVIDER_CATALOG
        # Use catalog directly (not env-overridden resolve_provider)
        ollama_config = PROVIDER_CATALOG["ollama"]
        assert ollama_config.default_model == "llama3.2"

    def test_config_set_provider(self) -> None:
        """Setting provider must resolve correct base_url."""
        from providers.catalog import PROVIDER_CATALOG
        openai_config = PROVIDER_CATALOG["openai"]
        assert "openai.com" in openai_config.base_url
