"""
OpenForge — TUI Input (v4.5.0)
==================================

Encapsulates the ``prompt_toolkit.PromptSession`` wired for the TUI:
multiline support, file-based history, and the ``patch_stdout`` handshake
that lets ``rich.live.Live`` redraw the terminal while the user is typing.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from ui_tui.core.theme import ACCENT, SUCCESS


_PROMPT_HTML = "<forge>forge</forge> <b>&gt;</b> "


def _hist_path() -> Path:
    p = Path.home() / ".openforge" / "tui_history"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def make_prompt_style() -> Style:
    """Toolbar + prompt colours."""
    return Style.from_dict(
        {
            "forge": f"fg:{SUCCESS} bold",
            "prompt": f"fg:{ACCENT}",
        }
    )


class NexaPromptSession:
    """
    Prompt session tuned for the TUI.

    Uses ``prompt_toolkit.PromptSession`` with:
      - ``FileHistory``  — persists across restarts (``~/.openforge/tui_history``)
      - ``patch_stdout`` — lets ``rich.live.Live`` paint while user types
      - ``multiline``    — Enter submits, Escape+Enter inserts a newline
    """

    def __init__(self) -> None:
        self._session = PromptSession(
            history=FileHistory(str(_hist_path())),
            style=make_prompt_style(),
            multiline=False,
            complete_while_typing=True,
            enable_history_search=True,
        )

    async def prompt(self, prefill: str = "") -> str:
        """
        Prompt the user and return the raw text.

        Returns:
            The submitted string (may be empty on Ctrl-C with empty buffer).

        Raises:
            KeyboardInterrupt / EOFError on user-initiated exit.
        """
        kwargs: dict = {"default": prefill} if prefill else {}
        return await self._session.prompt_async(_PROMPT_HTML, **kwargs)

    @property
    def raw_session(self) -> PromptSession:
        return self._session


__all__ = ["NexaPromptSession", "make_prompt_style"]
