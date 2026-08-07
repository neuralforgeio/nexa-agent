"""
Nexa Agent — Storage Layer (SQLite + FTS5)
==========================================

This module provides :class:`ConversationDB`, an async SQLite persistence
layer for conversations, messages, long-term memories, and the learning
graph.

Schema overview:
    conversations   — conversation metadata (id, title, timestamps, parent)
    messages        — individual messages (role, content, tool_name)
    memories        — curated long-term memories (the "getting smarter" store)
    learning_graph  — edges tracking tool success rates and patterns
    sessions        — session-split chain (parent_session_id for compression)

FTS5 virtual tables provide full-text search across messages and memories.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import time
import uuid
from typing import Any, Dict, List, Optional

import aiosqlite

from .config import NEXA_DB_PATH, NEXA_HOME

#: The SQL schema applied on initialization.
SCHEMA = """
-- Conversations: top-level chat threads.
CREATE TABLE IF NOT EXISTS conversations (
    id               TEXT PRIMARY KEY,
    title            TEXT DEFAULT 'untitled session',
    parent_session_id TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

-- Messages: individual turns within a conversation.
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tool_name       TEXT,
    token_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

-- Memories: curated long-term insights distilled by the memory curator.
-- These persist across sessions and make the agent "smarter over time".
CREATE TABLE IF NOT EXISTS memories (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    content    TEXT NOT NULL,
    source     TEXT DEFAULT 'conversation',
    confidence REAL DEFAULT 0.5,
    times_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);

-- Learning graph: tracks which tools/patterns lead to successful outcomes.
CREATE TABLE IF NOT EXISTS learning_graph (
    id         TEXT PRIMARY KEY,
    node_type  TEXT NOT NULL,
    node_value TEXT NOT NULL,
    success    INTEGER DEFAULT 0,
    failure    INTEGER DEFAULT 0,
    last_seen  TEXT NOT NULL,
    UNIQUE(node_type, node_value)
);

-- FTS5: full-text search across messages.
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content, content='messages', content_rowid='rowid'
);

-- FTS5: full-text search across memories.
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, content='memories', content_rowid='rowid'
);

-- Triggers: keep FTS indexes in sync.
-- v4.1.0: add AFTER DELETE + AFTER UPDATE triggers so that deleted rows
-- don't linger as orphaned FTS entries (previously only INSERT existed,
-- so a deleted message would still appear in FTS search results).
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;
"""

#: WAL mode pragma for better concurrent read performance.
PRAGMAS = "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    """Generate a unique ID with the given prefix using uuid4."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class ConversationDB:
    """
    Async SQLite persistence for conversations, messages, memories, and
    the learning graph.

    All methods are async and open a fresh connection per call. The database
    file lives at ``NEXA_HOME/nexa.db`` (default ``~/.nexa/nexa.db``).
    """

    async def init(self) -> None:
        """
        Create the database file, tables, FTS indexes, and triggers.

        Enables WAL mode for better concurrent read performance. Safe to
        call multiple times — uses ``IF NOT EXISTS`` on all DDL.
        """
        NEXA_HOME.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.executescript(PRAGMAS)
            await db.executescript(SCHEMA)
            # F-04: safe additive columns for pin/archive. SQLite has no
            # "ADD COLUMN IF NOT EXISTS", so probe via PRAGMA first.
            await self._ensure_column(db, "conversations", "pinned", "INTEGER DEFAULT 0")
            await self._ensure_column(db, "conversations", "archived", "INTEGER DEFAULT 0")
            await db.commit()

    @staticmethod
    async def _ensure_column(db: aiosqlite.Connection, table: str, name: str, ddl: str) -> None:
        """ALTER TABLE ADD COLUMN only when missing (idempotent migration)."""
        cursor = await db.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in await cursor.fetchall()]
        if name not in cols:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    async def create_conversation(
        self, title: str = "new session", parent_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            title:             The conversation title.
            parent_session_id: If this is a compressed split, the parent's ID.

        Returns:
            A dict with id, title, parent_session_id, created_at, updated_at.
        """
        cid = _uid("conv")
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO conversations (id, title, parent_session_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, title, parent_session_id, now, now),
            )
            await db.commit()
        return {
            "id": cid,
            "title": title,
            "parent_session_id": parent_session_id,
            "created_at": now,
            "updated_at": now,
        }

    async def list_conversations(
        self,
        limit: int = 100,
        query: str = "",
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List conversations newest-first (pinned first).

        F-03: ``query`` filters case-insensitively over the title and, when a
        plain word (FTS5-safe), over message content via the messages_fts
        virtual table. Unsafe queries fall back to title-only matching.
        F-04: archived conversations are hidden unless ``include_archived``.
        """
        q = query.strip()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row

            match_ids: Optional[set] = None
            if q:
                like = f"%{q.lower()}%"
                try:
                    # FTS5 match over message content.
                    cur = await db.execute(
                        "SELECT DISTINCT m.conversation_id AS cid FROM messages m "
                        "JOIN messages_fts f ON f.rowid = m.rowid "
                        "WHERE messages_fts MATCH ?",
                        (q,),
                    )
                    match_ids = {r[0] for r in await cur.fetchall()}
                except Exception:
                    # Unsafe FTS query characters (e.g. "*", quotes) — degrade
                    # gracefully to a plain content substring scan.
                    cur = await db.execute(
                        "SELECT DISTINCT conversation_id FROM messages "
                        "WHERE lower(content) LIKE ?",
                        (like,),
                    )
                    match_ids = {r[0] for r in await cur.fetchall()}

                sql = (
                    "SELECT id, title, parent_session_id, created_at, updated_at, "
                    "pinned, archived FROM conversations WHERE "
                    + ("" if include_archived else "COALESCE(archived,0)=0 AND ")
                    + "(lower(title) LIKE ? OR id IN (SELECT value FROM json_each(?))) "
                    "ORDER BY COALESCE(pinned,0) DESC, updated_at DESC LIMIT ?"
                )
                import json as _json
                cursor = await db.execute(
                    sql, (like, _json.dumps(sorted(match_ids)) if match_ids else "[]", limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT id, title, parent_session_id, created_at, updated_at, "
                    "pinned, archived FROM conversations "
                    + ("" if include_archived else "WHERE COALESCE(archived,0)=0 ")
                    + "ORDER BY COALESCE(pinned,0) DESC, updated_at DESC LIMIT ?",
                    (limit,),
                )
            rows = [dict(r) for r in await cursor.fetchall()]
            # Normalize legacy rows (pre-F-04) that may lack the value.
            for r in rows:
                r["pinned"] = bool(r.get("pinned") or 0)
                r["archived"] = bool(r.get("archived") or 0)
            return rows

    async def set_conversation_flags(
        self,
        conversation_id: str,
        pinned: Optional[bool] = None,
        archived: Optional[bool] = None,
    ) -> bool:
        """
        F-04: set pinned / archived flags on a conversation.

        Returns True when the row exists (even if flags are unchanged).
        """
        sets: List[str] = []
        vals: List[Any] = []
        if pinned is not None:
            sets.append("pinned = ?")
            vals.append(1 if pinned else 0)
        if archived is not None:
            sets.append("archived = ?")
            vals.append(1 if archived else 0)
        if not sets:
            return True
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            cursor = await db.execute(
                f"UPDATE conversations SET {', '.join(sets)} WHERE id = ?",
                (*vals, conversation_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a conversation, oldest first."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, role, content, tool_name, token_count, created_at "
                "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        token_count: int = 0,
    ) -> str:
        """Append a message to a conversation and update its timestamp."""
        mid = _uid("msg")
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, tool_name, token_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, conversation_id, role, content, tool_name, token_count, now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            await db.commit()
        return mid

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            await db.commit()
        return True

    async def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """
        Update a conversation's title.

        Args:
            conversation_id: The conversation ID.
            title:           The new title (already trimmed).

        Returns:
            ``True`` if the row was updated, else ``False``.
        """
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            cursor = await db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def branch_conversation(
        self, source_conversation_id: str, up_to_message_id: str, stop_after: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Fork a conversation: create a new conversation containing the source
        conversation's messages up to (and including) ``up_to_message_id``.

        v4.6.5 (F-02): used by the "Branch" action in the Web UI to spawn an
        alternative conversation thread from any point in history.

        Args:
            source_conversation_id: The conversation to copy messages from.
            up_to_message_id:       Inclusive upper bound of the copied prefix.
            stop_after:             If True (default) the message with the
                                    given id is INCLUDED in the branch; if
                                    False it is EXCLUDED (useful for "edit &
                                    resubmit" where the user message is the
                                    branching point but will be replaced).

        Returns:
            A dict with the new conversation's ``id``, ``title``,
            ``created_at`` and ``updated_at``, or ``None`` if the source
            conversation or message id does not exist.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            # 1. Source conversation must exist.
            cur = await db.execute(
                "SELECT id, title FROM conversations WHERE id = ?",
                (source_conversation_id,),
            )
            src = await cur.fetchone()
            if src is None:
                return None

            # 2. Source messages in chronological order.
            cur = await db.execute(
                "SELECT id, role, content, tool_name, token_count, created_at "
                "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (source_conversation_id,),
            )
            messages = [dict(r) for r in await cur.fetchall()]
            if not messages:
                return None

            # 3. Locate the cut-off index.
            idx = -1
            for i, m in enumerate(messages):
                if m["id"] == up_to_message_id:
                    idx = i
                    break
            if idx == -1:
                return None
            end = idx + (1 if stop_after else 0)
            prefix = messages[:end]
            if not prefix:
                return None

            # 4. Create the new conversation and copy messages (fresh ids, fresh timestamps).
            new_id = _uid("conv")
            now = _now_iso()
            title = f"{src['title']} (branch)" if src["title"] else "new branch"
            await db.execute(
                "INSERT INTO conversations (id, title, parent_session_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (new_id, title, source_conversation_id, now, now),
            )
            for m in prefix:
                await db.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, tool_name, token_count, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (_uid("msg"), new_id, m["role"], m["content"], m["tool_name"], m["token_count"], now),
                )
            await db.commit()
            return {
                "id": new_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }

    async def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Full-text search across all messages via FTS5.

        Args:
            query: The search query (FTS5 syntax).
            limit: Max results.

        Returns:
            List of matching message dicts.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT m.id, m.conversation_id, m.role, m.content, m.tool_name, m.created_at "
                "FROM messages_fts f JOIN messages m ON m.rowid = f.rowid "
                "WHERE messages_fts MATCH ? LIMIT ?",
                (query, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Memories (the "getting smarter" store)
    # ------------------------------------------------------------------
    async def add_memory(
        self,
        kind: str,
        content: str,
        source: str = "conversation",
        confidence: float = 0.5,
    ) -> str:
        """
        Store a curated long-term memory.

        Memories are distilled insights that persist across sessions,
        making the agent progressively smarter. The memory curator
        creates these after analyzing conversation patterns.

        Args:
            kind:       Memory category ('insight', 'preference', 'fact', 'skill').
            content:    The memory text.
            source:     Where it came from ('conversation', 'curator', 'user').
            confidence: 0.0–1.0 confidence score.

        Returns:
            The new memory ID.
        """
        mid = _uid("mem")
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO memories (id, kind, content, source, confidence, times_used, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (mid, kind, content, source, confidence, now, now),
            )
            await db.commit()
        return mid

    async def list_memories(self, kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List memories, optionally filtered by kind.

        Returns memories sorted by confidence (descending), then recency.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            if kind:
                cursor = await db.execute(
                    "SELECT * FROM memories WHERE kind = ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                    (kind, limit),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM memories ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(r) for r in await cursor.fetchall()]

    async def search_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search across memories via FTS5."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT m.* FROM memories_fts f JOIN memories m ON m.rowid = f.rowid "
                "WHERE memories_fts MATCH ? ORDER BY m.confidence DESC LIMIT ?",
                (query, limit),
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def increment_memory_usage(self, memory_id: str) -> None:
        """Increment the times_used counter when a memory is referenced."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "UPDATE memories SET times_used = times_used + 1, updated_at = ? WHERE id = ?",
                (_now_iso(), memory_id),
            )
            await db.commit()

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()
        return True

    # ------------------------------------------------------------------
    # Learning graph (pattern tracking)
    # ------------------------------------------------------------------
    async def record_outcome(
        self, node_type: str, node_value: str, success: bool
    ) -> None:
        """
        Record a tool/pattern outcome in the learning graph.

        The learning graph tracks which tools and patterns lead to
        successful outcomes, enabling the agent to make better decisions
        over time.

        Args:
            node_type:  'tool', 'pattern', 'approach'.
            node_value: The tool name or pattern identifier.
            success:    True if the outcome was successful.
        """
        now = _now_iso()
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            await db.execute(
                "INSERT INTO learning_graph (id, node_type, node_value, success, failure, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(node_type, node_value) DO UPDATE SET "
                "success = success + ?, failure = failure + ?, last_seen = ?",
                (
                    _uid("lg"),
                    node_type,
                    node_value,
                    1 if success else 0,
                    0 if success else 1,
                    now,
                    1 if success else 0,
                    0 if success else 1,
                    now,
                ),
            )
            await db.commit()

    async def get_success_rate(self, node_type: str, node_value: str) -> Optional[float]:
        """
        Get the success rate (0.0–1.0) for a tool/pattern.

        Returns None if the node has never been recorded.
        """
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            cursor = await db.execute(
                "SELECT success, failure FROM learning_graph WHERE node_type = ? AND node_value = ?",
                (node_type, node_value),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            total = row[0] + row[1]
            return row[0] / total if total > 0 else None

    async def get_learning_stats(self) -> Dict[str, Any]:
        """Get aggregate learning statistics for the /doctor command."""
        async with aiosqlite.connect(str(NEXA_DB_PATH)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM conversations")
            conv_count = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM messages")
            msg_count = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM memories")
            mem_count = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM learning_graph")
            lg_count = (await cursor.fetchone())[0]
            cursor = await db.execute(
                "SELECT node_value, success, failure FROM learning_graph "
                "WHERE node_type = 'tool' ORDER BY (success + failure) DESC LIMIT 10"
            )
            tool_stats = [
                {"tool": r[0], "success": r[1], "failure": r[2]}
                for r in await cursor.fetchall()
            ]
        return {
            "conversations": conv_count,
            "messages": msg_count,
            "memories": mem_count,
            "learning_nodes": lg_count,
            "tool_stats": tool_stats,
        }
