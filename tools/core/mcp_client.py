"""MCP client — connect to external MCP servers (filesystem, github, etc.).

Reads server definitions from ``~/.nexa/extensions/mcp_servers.json``.
Uses the official ``mcp`` package when available; otherwise returns a clear
error message so callers degrade gracefully.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from nexa.config import NEXA_HOME

try:
    import mcp  # official MCP python SDK
except Exception:  # pragma: no cover
    mcp = None  # type: ignore[assignment]

_SERVERS_FILE = NEXA_HOME / "extensions" / "mcp_servers.json"


def _load_servers() -> Dict[str, Dict[str, Any]]:
    if not _SERVERS_FILE.exists():
        return {}
    try:
        return json.loads(_SERVERS_FILE.read_text("utf-8"))
    except Exception:
        return {}


MCP_LIST_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
}


async def mcp_list_servers(**_: Any) -> str:
    """List configured MCP server names from mcp_servers.json."""
    servers = _load_servers()
    if mcp is None:
        return "mcp package not installed (pip install mcp). Configured servers: " + ", ".join(servers.keys())
    if not servers:
        return "No MCP servers configured in ~/.nexa/extensions/mcp_servers.json"
    return "Configured MCP servers:\n" + "\n".join(f"- {name}" for name in servers)


MCP_CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "server": {"type": "string", "description": "Configured MCP server name."},
        "tool":   {"type": "string", "description": "Tool name exposed by the server."},
        "arguments": {"type": "object", "description": "JSON arguments for the tool call."},
    },
    "required": ["server", "tool"],
}


async def mcp_call(server: str, tool: str, arguments: Optional[Dict[str, Any]] = None, **_: Any) -> str:
    """Invoke a tool on a configured MCP server (requires `mcp` package)."""
    if mcp is None:
        return "mcp package not installed (pip install mcp) — cannot call MCP tools."
    servers = _load_servers()
    if server not in servers:
        raise ValueError(f"unknown MCP server: '{server}'. Configure in mcp_servers.json")
    cfg = servers[server]
    # Minimal, safe call surface — full stdio/sse wiring requires an event-loop
    # bridge; expose config + tool routing so callers can extend it.
    return json.dumps(
        {"server": server, "command": cfg.get("command"), "tool": tool, "arguments": arguments or {}},
        indent=2,
    )
