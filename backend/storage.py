"""
Nexa Agent — Conversation Storage (SQLite via aiosqlite)
========================================================

This module provides :class:`ConversationDB`, an async wrapper around
SQLite for persisting conversations and messages.

Schema:
    conversations (id, title, created_at, updated_at)
    messages      (id, conversation_id, role, content, tool_name, created_at)

The database file lives at ``NEXA_HOME/nexa.db`` (default ``~/.nexa/nexa.db``).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import time
from typing import Any, Dict, List, Optional

import aiosqlite

from config import NEXA_DB_PATH, NEXA_HOME

#: The SQL schema applied on initialization.
SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT DEFAULT 'untitled session',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tool_name       TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
"""


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class ConversationDB:
    """
    Async SQLite persistence for conversations and messages.

    All methods are async and open a fresh connection per call (aiosqlite
    is lightweight enough that this is fine for a single-server deployment).
    """

    async def init(self) -> None:
        """
        Create the database file and tables if they don't exist.

        Also ensures ``NEXA_HOME`` exists.
        """
        NEXA_HOME.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def create_conversation(self, title: str = "new session") -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            title: The conversation title (defaults to ``"new session"``).

        Returns:
            A dict with ``id``, ``title``, ``created_at``, ``updated_at``.
        """
        cid = f"conv-{int(time.time() * 1000)}"
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (cid, title, now, now),
            )
            await db.commit()
        return {"id": cid, "title": title, "created_at": now, "updated_at": now}

    async def list_conversations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List conversations, newest first.

        Args:
            limit: Maximum number of conversations to return.

        Returns:
            A list of dicts with ``id``, ``title``, ``created_at``, ``updated_at``.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation, oldest first.

        Args:
            conversation_id: The conversation ID.

        Returns:
            A list of message dicts with ``id``, ``role``, ``content``,
            ``tool_name``, ``created_at``.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, role, content, tool_name, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
    ) -> str:
        """
        Append a message to a conversation and update its ``updated_at``.

        Args:
            conversation_id: The conversation ID.
            role:            The message role (``"user"``, ``"assistant"``, ``"tool"``).
            content:         The message content.
            tool_name:       If role is ``"tool"``, the name of the tool that produced this.

        Returns:
            The new message ID.
        """
        mid = f"msg-{int(time.time() * 1000)}"
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, tool_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mid, conversation_id, role, content, tool_name, now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            await db.commit()
        return mid

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: The conversation ID.

        Returns:
            ``True`` always (even if the conversation didn't exist).
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            await db.commit()
        return True
