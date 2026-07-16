"""
Nexa Agent — Prompt Builder
===========================

Assembles the system prompt dynamically from the agent identity, the tool
catalog, and any long-term memory context.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from typing import TYPE_CHECKING

from nexa_constants import NEXA_NAME, NEXA_TAGLINE, NEXA_VERSION

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


def build_system_prompt(registry: "ToolRegistry", memory_digest: str = "") -> str:
    """
    Build the system prompt for the agent.

    The prompt includes:
        - Agent identity (name, version, tagline).
        - The tool catalog (names + descriptions).
        - Long-term memory digest (if any).

    Args:
        registry:      The tool registry (to list available tools).
        memory_digest: An optional memory summary string.

    Returns:
        The full system prompt string.
    """
    tool_catalog = registry.describe()
    parts = [
        f"You are {NEXA_NAME} v{NEXA_VERSION}, an advanced AI agent.",
        NEXA_TAGLINE + ".",
        "",
        "You reason step by step and may use tools to ground your answers.",
        "Be concise, accurate and helpful. When you need to use a tool, call",
        "it via the function-calling interface and stop; the runtime will",
        "execute it and feed the result back to you.",
        "",
        "# Tools",
        "You have access to the following tools:",
        "",
        tool_catalog,
        "",
    ]
    if memory_digest:
        parts.extend(["# Long-term memory", memory_digest, ""])
    return "\n".join(parts)
