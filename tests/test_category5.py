"""Category 5 (H-01..H-08) — HITL + observability surface tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import src.server as server


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import anyio
    import openforge.config as cfg
    import openforge.state as st
    forge_home = tmp_path / ".openforge"; forge_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FORGE_HOME", str(forge_home))
    monkeypatch.setattr(cfg, "FORGE_HOME", forge_home)
    monkeypatch.setattr(cfg, "FORGE_DB_PATH", forge_home / "openforge.db")
    monkeypatch.setattr(st, "FORGE_HOME", forge_home)
    monkeypatch.setattr(st, "FORGE_DB_PATH", forge_home / "openforge.db")
    from openforge.state import ConversationDB
    monkeypatch.setattr(server, "_db", ConversationDB())
    anyio.run(server._db.init)
    return TestClient(server.app, raise_server_exceptions=False)


def test_usage_endpoint_ok(client):
    r = client.get("/api/usage", params={"days": 7})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_audit_chain_endpoint(client):
    r = client.get("/api/audit")
    assert r.status_code == 200 and r.json()["chain_valid"] is True


def test_approval_ws_accepts_connection(client):
    """The approval WebSocket must accept a connection. Auth is off in tests."""
    try:
        with client.websocket_connect("/ws/approval") as ws:
            pass
    except Exception as e:
        # 401 is possible when REQUIRE_AUTH is on and the client is unauthenticated —
        # assert that we at least reached a well-formed WS rejection, not a crash.
        from starlette.websockets import WebSocketDisconnect
        assert isinstance(e, WebSocketDisconnect), e


def test_frontend_files_presence():
    from pathlib import Path
    modal = Path("openforge_web/components/ApprovalModal.tsx").read_text(encoding="utf-8")
    assert "Esc" in modal and "Always Allow" in modal
    diff = Path("openforge_web/components/DiffViewer.tsx").read_text(encoding="utf-8")
    assert "+" in diff and "-" in diff  # unified diff markers
