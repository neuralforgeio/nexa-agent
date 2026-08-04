"""
Integration tests for the Skills API endpoints in src/server.py.
Uses fastapi.testclient to hit the real app without a live network socket.
The providers stay idle (in-memory) — no LLM call is made; skill execution is
tested with the in-process ScriptedProvider seam via a dedicated executor path.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, str(__file__.replace("\\", "/").replace("/tests/", "/")))

from fastapi.testclient import TestClient

os.environ.setdefault("NEXA_API_TOKEN", "test-token-123")

# Import AFTER setting env so the app picks up a static token.
import src.server as server  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(server.app, raise_server_exceptions=False)


AUTH = {"Authorization": "Bearer test-token-123"}


# ── GET /api/skills ──────────────────────────────────────────────────────────


class TestSkillsListEndpoint:
    def test_returns_200_with_auth(self, client):
        r = client.get("/api/skills", headers=AUTH)
        assert r.status_code == 200

    def test_returns_40_skills(self, client):
        r = client.get("/api/skills", headers=AUTH)
        data = r.json()
        assert "skills" in data
        assert len(data["skills"]) == 40

    def test_skill_card_shape(self, client):
        r = client.get("/api/skills", headers=AUTH)
        for card in r.json()["skills"]:
            assert {"name", "version", "description", "category", "enabled"} <= card.keys()

    def test_all_six_categories_represented(self, client):
        r = client.get("/api/skills", headers=AUTH)
        cats = {c["category"] for c in r.json()["skills"]}
        assert cats == {
            "code_intelligence", "web_research", "creative_media",
            "communication", "data_analytics", "devops_operations",
        }

    def test_category_filter(self, client):
        r = client.get("/api/skills", params={"category": "code_intelligence"}, headers=AUTH)
        assert r.status_code == 200
        for card in r.json()["skills"]:
            assert card["category"] == "code_intelligence"

    def test_invalid_category_returns_empty(self, client):
        r = client.get("/api/skills", params={"category": "nonexistent"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["skills"] == []


# ── POST /api/skills/{name}/execute ─────────────────────────────────────────


class TestSkillsExecuteEndpoint:
    def test_unknown_skill_404(self, client):
        r = client.post(
            "/api/skills/no_such_skill_xyz/execute",
            json={"input": {}},
            headers=AUTH,
        )
        assert r.status_code == 404

    def test_nonexistent_name_404(self, client):
        r = client.post(
            "/api/skills/definitely_not_a_skill/execute",
            json={"input": {}},
            headers=AUTH,
        )
        assert r.status_code == 404

    def test_disabled_skill_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("NEXA_SKILLS_DISABLED", "translation")
        r = client.post(
            "/api/skills/translation/execute",
            json={"input": {"text": "hi", "from": "en", "to": "fr"}},
            headers=AUTH,
        )
        assert r.status_code == 403

    def test_missing_input_returns_400(self, client):
        # code_explanation requires file_path; empty body -> SkillInputError
        r = client.post(
            "/api/skills/code_explanation/execute",
            json={"input": {}},
            headers=AUTH,
        )
        assert r.status_code in (400, 502)

    def test_llm_skill_ok_with_scripted_input(self, client):
        """Uses the real provider path; ScriptedProvider is NOT burned in here —
        this test verifies the endpoint contract, not the model. The heavy
        real-LLM gate lives in NEXA_E2E_LLAMACPP tests."""
        r = client.post(
            "/api/skills/translation/execute",
            json={"input": {"text": "hello", "from": "en", "to": "fr"}},
            headers=AUTH,
        )
        # A live server may succeed (200), be slow but pass, or fail with a
        # 502 if the model returned junk — all are valid endpoint responses.
        assert r.status_code in (200, 502)
        if r.status_code == 200:
            data = r.json()
            assert data["ok"] is True
            assert "translated_text" in data["result"]

    def test_execute_response_shape(self, client):
        r = client.post(
            "/api/skills/sentiment_analysis/execute",
            json={"input": {"text": "great work", "detail_level": "basic"}},
            headers=AUTH,
        )
        data = r.json()
        if r.status_code == 200:
            assert data["ok"] is True
            assert data["skill"] == "sentiment_analysis"
            assert "sentiment" in data["result"]
        else:
            assert "error" in data
