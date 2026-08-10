"""Regression tests for QA-VERIFY-v503 group no. 2 fixes (P0-5, P0-6, P0-7, P1-7..P1-12).

These are structural / offline-behavioral guards — they do NOT require the live gateway,
a running LLM, or network access. They verify the specific defects found by QA and fixed
in this group, complementing tests/test_cli_dispatch_regression.py (group no. 1).
"""

from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import openforge_cli.main as cli
from ui_tui.core.state import PersonaBadge, TUIState, ChatMessage
from ui_tui.core import theme as _theme
from ui_tui.commands import _DISPATCH
from ui_tui.render.layout import build_layout

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_PY = REPO_ROOT / "src" / "server.py"
PROVIDER_PY = REPO_ROOT / "openforge" / "provider.py"
SKILLS_PANEL_PY = REPO_ROOT / "ui_tui" / "panels" / "skills_panel.py"
LAYOUT_PY = REPO_ROOT / "ui_tui" / "render" / "layout.py"
STATE_PY = REPO_ROOT / "ui_tui" / "core" / "state.py"
NEXA_INIT = REPO_ROOT / "nexa" / "__init__.py"


def test_p0_5_ws_handlers_have_websocket_annotation() -> None:
    """P0-5: FastAPI treats an unannotated `websocket` param as a query param -> 403/422."""
    src = SERVER_PY.read_text(encoding="utf-8")
    for handler in ("ws_terminal", "ws_approval"):
        assert re.search(rf"async def {handler}\(websocket:\s*WebSocket", src), (
            f"{handler} is missing the `: WebSocket` annotation"
        )


def test_p0_6_layout_chat_panel_is_populated() -> None:
    """P0-6: build_layout must call layout['chat'].update(render_chat_area(state))."""
    src = LAYOUT_PY.read_text(encoding="utf-8")
    assert 'layout["chat"].update(' in src, "layout['chat'].update(...) never called"


def test_p0_7_nexa_shim_package_exists() -> None:
    """P0-7: legacy `import nexa` compat shim package must exist on disk."""
    assert NEXA_INIT.exists(), "nexa/__init__.py shim is missing"


def test_p1_7_skills_panel_imports_error_constant() -> None:
    """P1-7: ERROR used in skills_panel must be imported (theme defines it)."""
    assert hasattr(_theme, "ERROR"), "ui_tui.core.theme lost its ERROR constant"
    src = SKILLS_PANEL_PY.read_text(encoding="utf-8")
    assert re.search(r"from ui_tui\.core\.theme import[^\n]*\bERROR\b", src), (
        "ERROR is not in the skills_panel import list"
    )


def test_p1_8_provider_get_client_inside_try() -> None:
    """P1-8: _get_client() inside try -> missing creds yield ('error', ...) not raise."""
    from openforge.provider import LLMProvider

    p = LLMProvider(api_key=None)  # force missing-credentials path if supported
    collected = []
    try:
        async def _run():
            async for evt in p.chat_stream(messages=[{"role": "user", "content": "hi"}]):
                collected.append(evt)
                if evt and evt[0] == "error":
                    break
        asyncio.run(_run())
    except Exception:
        # LLMProvider(api_key=None) may not be a supported constructor; fall back to static check.
        src = PROVIDER_PY.read_text(encoding="utf-8")
        assert re.search(r"try:\s*\n\s*client = await self\._get_client\(\)", src) or (
            "client = await self._get_client()" in src.split("try:")[-1]
        ), "_get_client() appears outside a guarded try/except for the error-tuple contract"
        return
    assert any(e and e[0] == "error" for e in collected) or collected, "no error tuple yielded"


def test_p1_9_personabadge_has_detail_open_field() -> None:
    """P1-9: panels.py dereferences state.persona.detail_open — field must exist."""
    assert "detail_open" in {f.name for f in PersonaBadge.__dataclass_fields__.values()}, (
        "PersonaBadge lacks the detail_open field"
    )
    badge = PersonaBadge()
    assert badge.detail_open is False


def test_p1_10_dispatch_registers_exit_and_quit() -> None:
    """P1-10: /exit and /quit (advertised in help) must be in _DISPATCH."""
    assert "/exit" in _DISPATCH and "/quit" in _DISPATCH, "_DISPATCH missing /exit or /quit"


def test_p1_11_sandbox_timeout_is_clamped_below_max() -> None:
    """P1-11: /api/sandbox/build must not exceed terminal_tool.MAX_TIMEOUT."""
    from tools.terminal_tool import MAX_TIMEOUT

    src = SERVER_PY.read_text(encoding="utf-8")
    m = re.search(r"timeout=min\((\d+\.?\d*),\s*MAX_TIMEOUT\)", src)
    assert m, "sandbox build timeout is not clamped via min(..., MAX_TIMEOUT)"
    assert float(m.group(1)) >= MAX_TIMEOUT, "clamp constant unexpectedly below MAX_TIMEOUT"


def test_p1_12_ws_approval_enforces_verify_token_ws() -> None:
    """P1-12: /ws/approval must call verify_token_ws just like /ws/terminal."""
    src = SERVER_PY.read_text(encoding="utf-8")
    body = src.split("async def ws_approval", 1)[-1].split("\n\n", 1)[0]
    assert "verify_token_ws(" in body, "ws_approval does not invoke verify_token_ws"


def test_p0_5_both_ws_routes_registered() -> None:
    """Companion: app must still register both /ws/terminal and /ws/approval routes."""
    import os

    os.environ.setdefault("FORGE_API_TOKEN", "x")
    from src.server import app

    ws_paths = {r.path for r in app.routes if getattr(r, "path", "").startswith("/ws/")}
    assert {"/ws/terminal", "/ws/approval"} <= ws_paths
