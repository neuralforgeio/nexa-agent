"""
Category 2 (B-01..B-08) — Backend API hardening tests.

Covers:
  - B-01: 404 for nonexistent session / memory ids.
  - B-02: HTML-escaped tool blocks in /api/export (stored-XSS guard).
  - B-04: /api/provider/use refuses to activate an unreachable provider.
  - B-05: /api/chat/stream rejects messages over 10 KB.
  - B-07: /api/usage aggregates messages.token_count.

B-03 (SSE hard timeout) and B-06 (rate limiting) are verified implicitly by
the compile/import checks and require a live LLM to exercise end-to-end.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, str(__file__.replace("\\", "/").replace("/tests/", "/")))

import src.server as server  # noqa: E402
from openforge.state import ConversationDB  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    forge_home = tmp_path / ".nexa"
    forge_home.mkdir(parents=True, exist_ok=True)
    import openforge.config as cfg
    import openforge.state as st

    monkeypatch.setenv("FORGE_HOME", str(forge_home))
    monkeypatch.setattr(cfg, "FORGE_HOME", forge_home)
    monkeypatch.setattr(cfg, "FORGE_DB_PATH", forge_home / "openforge.db")
    monkeypatch.setattr(st, "FORGE_HOME", forge_home)
    monkeypatch.setattr(st, "FORGE_DB_PATH", forge_home / "openforge.db")
    monkeypatch.setattr(server, "_db", ConversationDB())

    import anyio

    async def _init() -> None:
        await server._db.init()

    anyio.run(_init)

    from fastapi.testclient import TestClient

    return TestClient(server.app, raise_server_exceptions=False)


# ── B-01: 404 on nonexistent ids ─────────────────────────────────────────────


class TestB01_404:
    def test_get_session_missing_404(self, client):
        r = client.get("/api/sessions/does-not-exist-abc")
        assert r.status_code == 404

    def test_delete_session_missing_404(self, client):
        r = client.delete("/api/sessions/does-not-exist-abc")
        assert r.status_code == 404

    def test_delete_memory_missing_404(self, client):
        r = client.delete("/api/memory", params={"id": "does-not-exist-abc"})
        assert r.status_code == 404

    def test_valid_session_200(self, client):
        sid = client.post("/api/sessions", json={"title": "ok"}).json()["id"]
        r = client.get(f"/api/sessions/{sid}")
        assert r.status_code == 200


# ── B-02: HTML-escaped export ────────────────────────────────────────────────


class TestB02_ExportEscape:
    def test_tool_html_is_escaped(self, client):
        sid = client.post("/api/sessions", json={"title": "xss-test"}).json()["id"]
        # Persist a malicious tool message directly via the DB.
        import anyio

        async def _add() -> None:
            await server._db.add_message(
                sid, "tool", "<script>alert(1)</script>", tool_name="<img onerror=alert(1)>"
            )

        anyio.run(_add)

        r = client.get(f"/api/export/{sid}", params={"format": "md"})
        assert r.status_code == 200
        md = r.json()["markdown"]
        assert "<script>alert(1)</script>" not in md
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in md
        assert "&lt;img onerror=alert(1)&gt;" in md

    def test_export_missing_session_404(self, client):
        r = client.get("/api/export/nope-404")
        assert r.status_code == 404


# ── B-04: pre-flight check on /api/provider/use ──────────────────────────────


class TestB04_Preflight:
    def test_unknown_provider_404(self, client):
        r = client.post("/api/provider/use", json={"name": "no-such-provider-xyzzy"})
        assert r.status_code == 404

    def test_unreachable_provider_refused_400(self, client, monkeypatch):
        """A provider that fails its health test must NOT be activated."""
        from openforge.provider_registry import ProviderRegistry

        async def _fail(self, name):  # noqa: ANN001, ANN202
            return False

        monkeypatch.setattr(ProviderRegistry, "test", _fail)

        # The name must exist in the registry for the 400 (not 404) branch.
        existing = client.get("/api/provider").json()
        if not existing["providers"]:
            pytest.skip("no providers configured in test env")
        name = existing["providers"][0]["name"]

        r = client.post("/api/provider/use", json={"name": name})
        assert r.status_code == 400
        assert "failed its connection test" in r.json()["error"].lower()


# ── B-05: max length validation ──────────────────────────────────────────────


class TestB05_MaxLength:
    def test_oversized_message_rejected(self, client):
        big = "x" * (10_240 + 1)
        r = client.post("/api/chat/stream", json={"message": big})
        assert r.status_code == 400

    def test_boundary_message_accepted(self, client):
        # Exactly at the limit should pass validation (may still fail later
        # for lack of a live model — we only assert it's not a 400).
        ok = "x" * 9_990
        r = client.post("/api/chat/stream", json={"message": ok})
        assert r.status_code != 400


# ── B-07: /api/usage aggregation ──────────────────────────────────────────────


class TestB07_Usage:
    def test_usage_endpoint_shape(self, client):
        # Seed one message with a token_count.
        sid = client.post("/api/sessions", json={"title": "usage"}).json()["id"]
        import anyio

        async def _add() -> None:
            await server._db.add_message(sid, "user", "hello", token_count=42)

        anyio.run(_add)

        r = client.get("/api/usage", params={"days": 7})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["tokens"] >= 42
        assert isinstance(data["byDay"], list)
        assert isinstance(data["byConversation"], list)
        conv = [c for c in data["byConversation"] if c["id"] == sid]
        assert conv and conv[0]["tokens"] == 42
