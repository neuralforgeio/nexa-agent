"""
Nexa Agent — Ask Question Mode (v3.1.0)
========================================

A "quick Q&A" mode that bypasses tool-calling for instant responses. Useful
for simple factual questions ("what's the capital of France?") where the
overhead of building a tool catalog + iteration loop is wasted.

When ``quick_mode=True``:
    - No tools are passed to the LLM (saves tokens + latency).
    - The iteration budget is 1 (single round-trip, no tool-call loop).
    - The system prompt is simplified (no tool catalog section).
    - Memory + user_profile are still injected (personalization preserved).

This module exposes a thin helper + config flag. The actual integration
lives in ``run_agent.NexaAgent.run_streaming`` and
``agent.conversation_loop.run_conversation``.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


#: When True, the conversation loop runs in "quick mode" (no tools, 1 iteration).
QUICK_MODE_DEFAULT: bool = False


def should_use_quick_mode(message: str, *, force: Optional[bool] = None) -> bool:
    """
    Decide whether ``message`` should be answered in quick mode.

    If ``force`` is not None, it overrides the heuristic (explicit user choice
    via ``/ask`` slash command).

    The heuristic considers the message "quick-answerable" if it is:
      - Short (<= 12 words).
      - Does not contain action verbs (fix, write, read, run, search, install).
      - Does not contain a code reference (file path, function name).

    Args:
        message: The user's message.
        force:   Optional explicit override (``True`` / ``False``).

    Returns:
        ``True`` if quick mode should be used.

    Example:
        >>> should_use_quick_mode("What is the capital of France?")
        True
        >>> should_use_quick_mode("Read nexa-workspace/notes.txt and summarize")
        False
        >>> should_use_quick_mode("Fix the bug", force=True)
        True
    """
    if force is not None:
        return bool(force)
    stripped = message.strip()
    if not stripped:
        return False
    # Long messages likely need tools.
    if len(stripped.split()) > 12:
        return False
    lower = stripped.lower()
    # Action verbs that signal tool use.
    action_verbs = (
        "fix", "write", "read", "run", "search", "install", "create",
        "delete", "patch", "execute", "build", "deploy", "commit",
        "make", "generate", "find", "look up",
    )
    if any(verb in lower for verb in action_verbs):
        return False
    # File/code references signal tool use.
    if any(ext in lower for ext in (".py", ".js", ".ts", ".md", ".json", ".txt")):
        return False
    if "`" in stripped:  # backtick code reference
        return False
    return True


def build_quick_system_prompt(base_prompt: str) -> str:
    """
    Simplify the system prompt for quick mode (strip the tool catalog).

    In quick mode we don't expose tools to the LLM, so the "Available Tools"
    section is irrelevant. We strip it to save tokens + reduce confusion.

    Args:
        base_prompt: The full system prompt (with tool catalog section).

    Returns:
        A simplified prompt with the "# Available Tools" section removed.

    Example:
        >>> prompt = "# Agent Identity\\n...\\n\\n# Available Tools\\n...\\n\\n# Behavioral"
        >>> simplified = build_quick_system_prompt(prompt)
        >>> "# Available Tools" not in simplified
        True
    """
    # Naive section stripper: remove everything between "# Available Tools"
    # and the next "# " header (or end of string).
    import re
    pattern = re.compile(
        r"# Available Tools\n.*?(?=\n# |\Z)",
        re.DOTALL,
    )
    simplified = pattern.sub("", base_prompt)
    # Clean up any double blank lines left behind.
    simplified = re.sub(r"\n{3,}", "\n\n", simplified)
    return simplified.strip()


def is_quick_mode_enabled() -> bool:
    """Return True if quick mode is enabled via env (NEXA_QUICK_MODE=1)."""
    import os
    return os.environ.get("NEXA_QUICK_MODE", "0").lower() in ("1", "true", "yes")
