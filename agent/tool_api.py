"""
OpenForge — Tool API (v4.3.0)
==============================

Public extension point for user-built tools. Stability contract: this module's
public functions are semver-stable within a major release — signatures only
change on v5.0.0+.

Core capabilities surfaced to user tools (without letting them touch the
internals directly):

  * ``register_tool`` / ``unregister_tool`` / ``list_user_tools``
  * ``register_gateway`` / ``unregister_gateway`` / ``get_gateway``
  * ``workspace_path`` / ``read_workspace_file`` / ``write_workspace_file``
  * ``emit_event`` / ``on_event``
  * ``http_client`` (pre-configured httpx.AsyncClient with safety policy)

Together these are the *only* interfaces a tool author should need; anything
else (direct DB access, raw registry edits, os.environ walks) is intentionally
NOT exported.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# In-memory extension registry (single-process)
# ---------------------------------------------------------------------------

_USER_TOOLS: Dict[str, Dict[str, Any]] = {}
_USER_GATEWAYS: Dict[str, Any] = {}
_EVENT_HANDLERS: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}


def register_tool(name: str, handler: Callable, meta: Optional[Dict[str, Any]] = None) -> None:
    """
    Register a user-supplied tool.

    Args:
        name:    Unique tool name. Must not collide with built-ins.
        handler: Async callable. Signature: ``async def handler(**kwargs) -> str``.
        meta:    Optional manifest dict (permissions, description, author).

    Raises:
        ValueError: If the name is already registered.
    """
    if name in _USER_TOOLS:
        raise ValueError(f"tool already registered: {name}")
    _USER_TOOLS[name] = {
        "handler": handler,
        "meta": meta or {},
        "registered_at": __import__("time").time(),
    }


def unregister_tool(name: str) -> bool:
    """Remove a previously registered user tool. Returns True if removed."""
    return _USER_TOOLS.pop(name, None) is not None


def list_user_tools() -> List[Dict[str, Any]]:
    """Return metadata about every user-registered tool."""
    return [
        {
            "name": name,
            "meta": dict(entry["meta"]),
            "registered_at": entry["registered_at"],
        }
        for name, entry in _USER_TOOLS.items()
    ]


def get_user_tool_handler(name: str) -> Optional[Callable]:
    """Return the handler for a previously-registered user tool, or None."""
    entry = _USER_TOOLS.get(name)
    return entry["handler"] if entry else None


# ---------------------------------------------------------------------------
# Gateway registration
# ---------------------------------------------------------------------------

def register_gateway(name: str, gateway: Any) -> None:
    """Register a gateway instance (Telegram, Discord, Email, ...)."""
    if name in _USER_GATEWAYS:
        raise ValueError(f"gateway already registered: {name}")
    _USER_GATEWAYS[name] = gateway


def unregister_gateway(name: str) -> bool:
    return _USER_GATEWAYS.pop(name, None) is not None


def get_gateway(name: str) -> Any:
    return _USER_GATEWAYS.get(name)


def list_gateways() -> List[str]:
    return sorted(_USER_GATEWAYS.keys())


# ---------------------------------------------------------------------------
# Event bus (in-process only; one-shot)
# ---------------------------------------------------------------------------

def emit_event(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Emit an event. Handlers registered via :func:`on_event` are invoked
    synchronously in insertion order. No queue is kept — this is a fan-out
    for the current turn only.
    """
    handlers = _EVENT_HANDLERS.get(event_type, [])
    for handler in list(handlers):
        # Don't let one handler break the loop.
        try:
            # accept both async and sync handlers
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(handler):
                asyncio.create_task(handler(payload))  # fire-and-forget
            else:
                handler(payload)
        except Exception:
            continue


def on_event(event_type: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
    """Subscribe a handler to an event type. Handlers may be sync or async."""
    _EVENT_HANDLERS.setdefault(event_type, []).append(handler)


def off_event(event_type: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
    """Unsubscribe a handler, if present."""
    handlers = _EVENT_HANDLERS.get(event_type, [])
    try:
        handlers.remove(handler)
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Workspace helpers (sandboxed)
# ---------------------------------------------------------------------------

def workspace_path(rel: str) -> Path:
    """
    Resolve a WORKSPACE-relative path safely.

    Raises:
        ValueError: If the path escapes the workspace (via ``..``).
    """
    from tools._paths import resolve_in_workspace
    return resolve_in_workspace(rel)


async def read_workspace_file(rel: str) -> str:
    """Read a file within the workspace (UTF-8)."""
    p = workspace_path(rel)
    return p.read_text(encoding="utf-8", errors="replace")


async def write_workspace_file(rel: str, content: str) -> Path:
    """Write content into the workspace (atomic)."""
    import os
    p = workspace_path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(p))
    return p


# ---------------------------------------------------------------------------
# Sandbox HTTP client — preconfigured httpx.AsyncClient
# ---------------------------------------------------------------------------

def http_client(*, timeout: float = 30.0, follow_redirects: bool = True):
    """
    Return a pre-configured ``httpx.AsyncClient`` scoped for tool use.

    Currently only enforces a default User-Agent and timeout; allow/deny URL
    policy hooks are routed through the caller (tools should not generally be
    able to make outbound network calls without going through the Tool API).
    """
    import httpx

    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        headers={"User-Agent": "openforge-tool/4.3"},
    )
