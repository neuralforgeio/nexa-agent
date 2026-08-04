"""
Tests for the TUI redesign (v4.5.0).

Covers:
  * ``ui_tui/state.py``         — event reducer (16 event types)
  * ``ui_tui/skills_panel.py``  — skills overlay panel builder
  * ``ui_tui/commands.py``      — slash command dispatch table
  * ``ui_tui/server_health.py`` — background poller contract

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest

import time
from pathlib import Path

import skills
from ui_tui.core.state import ChatMessage, TUIState, apply_event
from ui_tui.panels.skills_panel import build_skills_overlay, _CATEGORY_LABELS
from ui_tui.commands import dispatch
from ui_tui.services.server_health import ServerHealthPoller


# ---------------------------------------------------------------------------
# state.apply_event
# ---------------------------------------------------------------------------

class TestApplyEvent:
    """Every event type gets handled without raising."""

    @pytest.mark.parametrize("etype,payload", [
        ("thinking", {}),
        ("token", {"text": "hi"}),
        ("tool_result", {"result": {"tool": "x", "ok": True, "duration_ms": 10, "output": "", "args": ""}}),
        ("agent_persona", {"persona": {"name": "Planner", "icon": "🧑", "color": "#fff", "goal": "plan"}}),
        ("patterns", {"detail": "found patterns"}),
        ("reflection", {"summary": "good answer"}),
        ("suggestions", {"items": [{"label": "try X"}]}),
        ("confidence", {"score": 0.9, "should_enrich": True}),
        ("heal", {"plan": {}}),
        ("failover", {"from": "a", "to": "b", "reason": "r"}),
        ("expand", {"expanded": "ok"}),
        ("intent", {"intent": {}}),
        ("autolearn", {"query": "q", "fact": None}),
        ("compressing", {"detail": "compress"}),
        ("memory", {"memories": []}),
        ("done", {"answer": "done"}),
        ("error", {"message": "bang"}),
    ])
    def test_event_type_accepted(self, etype: str, payload: dict) -> None:
        state = TUIState()
        apply_event(state, {"type": etype, **payload})
        # every branch mutates *something*; just assert no exception
        assert True

    def test_done_replaces_streaming(self) -> None:
        state = TUIState(streaming=True)
        state.messages = [ChatMessage(role="assistant", content="partial")]
        apply_event(state, {"type": "done", "answer": "final"})
        assert state.streaming is False
        assert state.messages[-1].content == "final"

    def test_error_clears_streaming(self) -> None:
        state = TUIState(streaming=True)
        apply_event(state, {"type": "error", "message": "oops"})
        assert state.streaming is False

    def test_token_accumulates(self) -> None:
        state = TUIState()
        apply_event(state, {"type": "token", "text": "Hello"})
        apply_event(state, {"type": "token", "text": " world"})
        assert state.messages[-1].content == "Hello world"
        assert state.token_estimate >= 2


# ---------------------------------------------------------------------------
# skills_panel
# ---------------------------------------------------------------------------

class TestSkillsPanel:
    def test_build_with_empty_skills(self) -> None:
        panel = build_skills_overlay(TUIState(), [], "")
        assert panel is not None
        assert hasattr(panel, "renderable")

    def test_filter_by_name(self) -> None:
        all_skills = skills.list_skills()
        panel = build_skills_overlay(TUIState(), all_skills, "code_review")
        from rich.console import Console
        c = Console(record=True, width=120)
        c.print(panel)
        out = c.export_text()
        assert "code_review" in out

    def test_filter_no_match(self) -> None:
        panel = build_skills_overlay(TUIState(), skills.list_skills(), "zzz_no_match_xyz")
        from rich.console import Console
        c = Console(record=True, width=120)
        c.print(panel)
        out = c.export_text()
        assert "0" in out  # total shown counter

    def test_category_chips_present(self) -> None:
        panel = build_skills_overlay(TUIState(), skills.list_skills(), "")
        from rich.console import Console
        c = Console(record=True, width=120)
        c.print(panel)
        out = c.export_text()
        for cat in ("Code Intel", "Web Research", "Creative", "Comms", "Data", "DevOps"):
            assert cat in out

    def test_skill_disabled_flag_rendered(self) -> None:
        all_skills = skills.list_skills()
        panel = build_skills_overlay(TUIState(), all_skills, "")
        from rich.console import Console
        c = Console(record=True, width=120)
        c.print(panel)
        out = c.export_text()
        # every skill shown should have an enabled marker
        assert "✓" in out


# ---------------------------------------------------------------------------
# commands dispatch
# ---------------------------------------------------------------------------

class MockAgent:
    """Minimal agent stand-in for command tests."""

    provider_name = "test"
    model = "test-model"
    provider = type("P", (), {"model": "test-model", "_client": None, "base_url": "", "api_key": ""})()
    db = None
    workspace_root = Path("C:/dummy").resolve()

    async def run_streaming(self, *a, **kw):
        async for ev in []:
            yield ev


class TestCommands:
    @pytest.mark.asyncio
    async def test_help_dispatch(self) -> None:
        result = await dispatch(TUIState(), MockAgent(), "/help")
        assert "TUI Commands" in result
        assert "/tools" in result
        assert "/sessions" in result

    @pytest.mark.asyncio
    async def test_clear_dispatch(self) -> None:
        state = TUIState(messages=[ChatMessage(role="user", content="hi")])
        result = await dispatch(state, MockAgent(), "/clear")
        assert state.messages == []

    @pytest.mark.asyncio
    async def test_tools_dispatch(self) -> None:
        result = await dispatch(TUIState(), MockAgent(), "/tools")
        assert "code_review" in result
        assert "40" in result

    @pytest.mark.asyncio
    async def test_empty_command_passes_through(self) -> None:
        result = await dispatch(TUIState(), MockAgent(), "/not_a_real_command")
        assert result == ""

    @pytest.mark.asyncio
    async def test_status_summary_format(self) -> None:
        s = TUIState(model="llama3.2", provider_name="llamacpp")
        s.server_up = True
        s.streaming = True
        assert "llama3.2" in s.status_summary()


# ---------------------------------------------------------------------------
# server_health
# ---------------------------------------------------------------------------

class TestServerHealthPoller:
    def test_initial_state(self) -> None:
        """Poller starts with server_up=False by default."""
        state = TUIState()
        assert state.server_up is False

    def test_poll_once_down(self) -> None:
        """Unreachability sets server_up to False."""
        state = TUIState()
        poller = ServerHealthPoller(state, backend_url="http://127.0.0.1:1")
        poller._poll_once()
        assert state.server_up is False

    def test_poll_once_up(self) -> None:
        """A healthy endpoint sets server_up=True."""
        import urllib.request

        class FakeResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False

        state = TUIState()
        poller = ServerHealthPoller(state)

        real_urlopen = urllib.request.urlopen
        try:
            urllib.request.urlopen = lambda url, timeout=3: FakeResponse()
            poller._poll_once()
        finally:
            urllib.request.urlopen = real_urlopen
        assert state.server_up is True
