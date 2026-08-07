"""
Backend tests for F-03 (session search), F-04 (pin/archive flags) and
F-11 (POST /api/upload multipart endpoint).

Runs against the real FastAPI app via fastapi.testclient with an isolated
NEXA_HOME so the real conversation database is never touched.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import io
import os
import sys

import pytest

sys.path.insert(0, str(__file__.replace("\\", "/").replace("/tests/", "/")))

import src.server as server  # noqa: E402
from nexa.state import ConversationDB  # noqa: E402


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Point the app's database at a temp directory and reinitialise it."""
    nexa_home = tmp_path / ".nexa"
    nexa_home.mkdir(parents=True, exist_ok=True)
    import nexa.config as cfg

    monkeypatch.setenv("NEXA_HOME", str(nexa_home))
    # NEXA_HOME / DB path are computed at import time — re-point them.
    monkeypatch.setattr(cfg, "NEXA_HOME", nexa_home)
    monkeypatch.setattr(cfg, "NEXA_DB_PATH", nexa_home / "nexa.db")

    import nexa.state as st
    monkeypatch.setattr(st, "NEXA_HOME", nexa_home)
    monkeypatch.setattr(st, "NEXA_DB_PATH", nexa_home / "nexa.db")
    monkeypatch.setattr(server, "_db", ConversationDB())

    import anyio

    async def _init() -> None:
        await server._db.init()

    anyio.run(_init)
    return server


@pytest.fixture()
def client(fresh_db):
    from fastapi.testclient import TestClient

    return TestClient(fresh_db.app, raise_server_exceptions=False)


# ── F-11: /api/upload ────────────────────────────────────────────────────────


class TestUploadEndpoint:
    def test_upload_text_file_returns_path(self, client):
        r = client.post(
            "/api/upload",
            files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["path"].startswith("uploads/")
        assert body["size"] == len(b"hello world")

    def test_upload_sanitizes_traversal_filename(self, client):
        """A hostile filename must not escape the uploads/ directory."""
        r = client.post(
            "/api/upload",
            files={"file": ("../../../etc/passwd.txt", io.BytesIO(b"x"), "text/plain")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["path"].startswith("uploads/")
        assert ".." not in os.path.normpath(body["path"]).split(os.sep)

    def test_upload_empty_file_rejected(self, client):
        r = client.post(
            "/api/upload",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
        assert r.status_code == 400


# ── F-03: GET /api/sessions?q= ───────────────────────────────────────────────


class TestSessionSearchEndpoint:
    def _seed(self, client):
        # Conversation whose TITLE matches "alpha".
        a = client.post("/api/sessions", json={"title": "alpha project"}).json()["id"]
        # Conversation whose MESSAGE CONTENT matches.

        client.post("/api/sessions", json={"title": "unrelated"}).json()["id"]
        return a

    def test_title_search_returns_match(self, client):
        self._seed(client)
        r = client.get("/api/sessions", params={"q": "alpha"})
        assert r.status_code == 200
        titles = [s["title"] for s in r.json()["sessions"]]
        assert any("alpha" in t for t in titles)

    def test_unmatched_query_returns_empty(self, client):
        self._seed(client)
        r = client.get("/api/sessions", params={"q": "zzznomatchzz12345"})
        assert r.status_code == 200
        assert r.json()["sessions"] == []


# ── F-04: PATCH pinned/archived flags ────────────────────────────────────────


class TestSessionFlagsEndpoint:
    def test_pin_and_archive_roundtrip(self, client):
        sid = client.post("/api/sessions", json={"title": "pinnable"}).json()["id"]

        r = client.patch(f"/api/sessions/{sid}", json={"pinned": True})
        assert r.status_code == 200

        listed = client.get("/api/sessions", params={"includeArchived": "true"}).json()
        row = next(s for s in listed["sessions"] if s["id"] == sid)
        assert row["pinned"] is True
        assert row["archived"] is False

        r2 = client.patch(f"/api/sessions/{sid}", json={"archived": True})
        assert r2.status_code == 200
        row2 = next(
            s
            for s in client.get("/api/sessions", params={"includeArchived": "true"}).json()["sessions"]
            if s["id"] == sid
        )
        assert row2["archived"] is True

    def test_flags_on_missing_session_404(self, client):
        r = client.patch("/api/sessions/no-such-id-999", json={"pinned": True})
        assert r.status_code in (404, 400)

    def test_empty_patch_rejected(self, client):
        sid = client.post("/api/sessions", json={"title": "noop"}).json()["id"]
        r = client.patch(f"/api/sessions/{sid}", json={})
        assert r.status_code == 400
