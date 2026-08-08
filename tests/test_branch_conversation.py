"""
Tests for F-02 branch_conversation (fork-at-message) in openforge.state.ConversationDB.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import pytest
import pytest_asyncio

from openforge.state import ConversationDB


@pytest_asyncio.fixture
async def tmp_db(tmp_path, monkeypatch):
    """Isolated DB in a temp dir so we never touch the real ~/.openforge/openforge.db."""
    import openforge.state as st
    monkeypatch.setattr(st, "FORGE_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(st, "FORGE_HOME", tmp_path)
    db = ConversationDB()
    await db.init()
    return db


class TestBranchConversation:
    @pytest.mark.asyncio
    async def test_happy_path_branches_prefix_including_message(self, tmp_db):
        src = await tmp_db.create_conversation("original")
        m1 = await tmp_db.add_message(src["id"], "user", "hello")
        m2 = await tmp_db.add_message(src["id"], "assistant", "hi there")
        m3 = await tmp_db.add_message(src["id"], "user", "follow up")

        br = await tmp_db.branch_conversation(src["id"], m2)
        assert br is not None
        assert "branch" in br["title"].lower()
        msgs = await tmp_db.get_messages(br["id"])
        # prefix includes m1 + m2, excludes m3
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["content"] == "hi there"
        # parent linkage
        assert br["id"] != src["id"]

    @pytest.mark.asyncio
    async def test_exclusive_stop_after_excludes_anchor(self, tmp_db):
        src = await tmp_db.create_conversation("original")
        m1 = await tmp_db.add_message(src["id"], "user", "first")
        m2 = await tmp_db.add_message(src["id"], "assistant", "second")
        br = await tmp_db.branch_conversation(src["id"], m2, stop_after=False)
        assert br is not None
        msgs = await tmp_db.get_messages(br["id"])
        assert [m["content"] for m in msgs] == ["first"]

    @pytest.mark.asyncio
    async def test_error_paths_return_none(self, tmp_db):
        src = await tmp_db.create_conversation("original")
        m1 = await tmp_db.add_message(src["id"], "user", "first")
        # unknown session
        assert await tmp_db.branch_conversation("conv-nope", m1) is None
        # unknown message id
        assert await tmp_db.branch_conversation(src["id"], "msg-nope") is None
        # empty source conversation (no messages → anchor can't exist)
        empty = await tmp_db.create_conversation("empty")
        assert await tmp_db.branch_conversation(empty["id"], "msg-anything") is None

    @pytest.mark.asyncio
    async def test_branch_gets_fresh_message_ids(self, tmp_db):
        src = await tmp_db.create_conversation("original")
        m1 = await tmp_db.add_message(src["id"], "user", "hello world")
        br = await tmp_db.branch_conversation(src["id"], m1)
        msgs = await tmp_db.get_messages(br["id"])
        assert msgs[0]["id"] != m1  # fresh id, not aliased to source row
