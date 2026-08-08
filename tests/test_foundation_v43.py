"""
Tests for the new Foundation layer (v4.3.0).

Covers:
  * ``openforge.tool_api`` registration, unregistration, listing, event bus.
  * ``gateways.base`` lifecycle and session mapping.
  * Both work cleanly under `pytest -q`.
"""

from __future__ import annotations

import asyncio

import pytest

from agent.tool_api import (
    emit_event,
    get_user_tool_handler,
    list_gateways,
    list_user_tools,
    on_event,
    register_gateway,
    register_tool,
    unregister_gateway,
    unregister_tool,
    workspace_path,
    write_workspace_file,
    read_workspace_file,
)
from gateways.base import GatewayBase, GatewayConfig


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
class TestToolAPIRegistration:
    def test_register_and_get(self):
        async def hello_tool(name: str = "world"):
            return f"hello {name}"

        register_tool("hello_tool", hello_tool, meta={"description": "test"})
        handler = get_user_tool_handler("hello_tool")
        assert handler is not None
        assert asyncio.run(handler()) == "hello world"

    def test_unregister(self):
        async def dummy():
            return "x"
        register_tool("x_del", dummy)
        assert unregister_tool("x_del") is True
        assert get_user_tool_handler("x_del") is None
        assert unregister_tool("x_del") is False  # second remove = no-op

    def test_list_includes_meta(self):
        async def dummy():
            return "x"
        register_tool("listed_tool", dummy, meta={"author": "test"})
        names = [t["name"] for t in list_user_tools()]
        assert "listed_tool" in names

    def test_register_duplicate_rejects(self):
        async def dummy():
            return "x"
        register_tool("dup_tool", dummy)
        with pytest.raises(ValueError):
            register_tool("dup_tool", dummy)

    def test_event_emit_and_subscribe(self):
        got: list[dict] = []
        def handler(payload):
            got.append(payload)
        on_event("test_event", handler)
        emit_event("test_event", {"msg": "hi"})
        assert got and got[0]["msg"] == "hi"


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------
class TestWorkspaceHelpers:
    def test_write_read_cycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
        asyncio.run(write_workspace_file("notes.md", "hello"))
        content = asyncio.run(read_workspace_file("notes.md"))
        assert "hello" in content

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError):
            workspace_path("../../../etc/passwd")


# ---------------------------------------------------------------------------
# Gateway base
# ---------------------------------------------------------------------------
class _EchoGateway(GatewayBase):
    name = "echo"

    async def start(self):
        self.mark_started()

    async def stop(self):
        self._started_at = None
        self._health = "stopped"

    async def health_check(self):
        return {"ok": self._started_at is not None}

    async def send_message(self, session_id: str, text: str):
        return {"echo": f"[{session_id}] {text}"}

    def format_reply(self, text: str) -> str:
        return f"echo: {text}"


class TestGatewayBase:
    def test_lifecycle(self):
        g = _EchoGateway(GatewayConfig(auth_token="x"))
        asyncio.run(g.start())
        s = asyncio.run(g.send_message("s1", "hi"))
        # send_message returns {"echo": "[session] text"}
        assert "[s1]" in s.get("echo", "") and "hi" in s.get("echo", "")
        asyncio.run(g.stop())
        hc = asyncio.run(g.health_check())
        assert hc["ok"] is False

    def test_session_mapping_stable(self):
        g = _EchoGateway(GatewayConfig())
        a = g.session_for("user-1")
        b = g.session_for("user-1")
        assert a == b
        assert a.startswith("echo-")

    def test_whitelist_guard(self):
        g = _EchoGateway(GatewayConfig(allowed_users=frozenset({"alice"})))
        assert asyncio.run(g.is_user_allowed("alice")) is True
        assert asyncio.run(g.is_user_allowed("bob")) is False


# ---------------------------------------------------------------------------
# Gateways register/unregister (test module registry helpers)
# ---------------------------------------------------------------------------
class TestGatewayRegistry:
    def test_register_unregister(self):
        g = _EchoGateway(GatewayConfig())
        register_gateway("echo", g)
        assert "echo" in list_gateways()
        assert unregister_gateway("echo") is True
        assert "echo" not in list_gateways()
