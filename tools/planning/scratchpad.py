"""
OpenForge — Planning Tools: Scratchpad + Think (v4.1.0)
=========================================================

Two tools:

- :func:`scratchpad_write` — the agent's working memory on disk
  (``.nexa/scratchpad.md``). Append or replace.
- :func:`think`            — a loop-back reasoning tool. The agent narrates
  an internal step (hypothesis, plan, next action); the tool echoes the
  thought back along with a prompt to continue. This pairs with the
  Working Process UI panel: every ``think`` call becomes a collapsible
  reasoning trace.

Both are stored per-workspace so multiple projects each get their own
scratchpad.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tools._paths import resolve_in_workspace as _resolve_in_workspace


def resolve_in_workspace(raw: str):
    """Module-level wrapper so tests can monkeypatch path resolution."""
    return _resolve_in_workspace(raw)


_SCRATCHPAD_REL = ".nexa/scratchpad.md"


def _scratchpad_path():
    """Return the absolute path for the workspace scratchpad."""
    ws = resolve_in_workspace(".")
    (ws / ".nexa").mkdir(parents=True, exist_ok=True)
    return ws / _SCRATCHPAD_REL


async def scratchpad_write(content: str, mode: str = "append", label: str = "") -> str:
    """
    Write to the workspace scratchpad (``.nexa/scratchpad.md``).

    Use this to remember intermediate results, hypotheses, partial plans —
    anything you need to recall in later tool calls but shouldn't put in
    the final answer.

    Args:
        content: The text to write.
        mode:    ``"append"`` (default) or ``"replace"``.
        label:   Optional label written as a ``## <label>`` heading.

    Returns:
        Confirmation with the current scratchpad size.
    """
    if not content.strip():
        return "**Error.** `content` cannot be empty."

    path = _scratchpad_path()
    header = f"\n\n## {label}\n\n" if label else "\n\n"
    body = content.rstrip() + "\n"

    if mode == "replace":
        path.write_text(header.lstrip() + body, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(header + body)

    size = path.stat().st_size
    return f"Scratchpad updated ({size} bytes, mode={mode})."


SCRATCHPAD_WRITE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "Text to write."},
        "mode": {"type": "string", "enum": ["append", "replace"], "default": "append"},
        "label": {"type": "string", "description": "Optional heading label.", "default": ""},
    },
    "required": ["content"],
}


async def think(thought: str, next_action: Optional[str] = None, confidence: float = 0.5) -> str:
    """
    Loop-back reasoning tool — narrate an internal step.

    Use this *before* taking an external action to make your reasoning
    explicit. The Working Process panel in the UI turns each call into a
    collapsible thinking trace.

    Args:
        thought:     The current reasoning step (one paragraph max).
        next_action: Optional tool you plan to call next (name only) or
                     free text describing what you'll do next.
        confidence:  Your confidence 0.0–1.0 that the current plan will work.

    Returns:
        An echo of the thought plus a structured prompt for the next step.
    """
    thought = thought.strip()
    if not thought:
        return "**Error.** `thought` cannot be empty."

    conf = max(0.0, min(1.0, float(confidence)))
    parts = [
        "💭 **Thinking**",
        "",
        f"> {thought}",
        "",
        f"_Confidence: {conf:.0%}_",
    ]
    if next_action:
        parts.append(f"_Next: {next_action}_")
    parts.append("")
    parts.append("_Continue reasoning, or take the planned action._")
    return "\n".join(parts)


THINK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "thought": {"type": "string", "description": "The current reasoning step."},
        "next_action": {"type": "string", "description": "What's next (tool name or free text).", "default": ""},
        "confidence": {"type": "number", "description": "Confidence 0.0–1.0.", "default": 0.5},
    },
    "required": ["thought"],
}
