"""
OpenForge — TUI Server-Health Poller (v4.5.0)
================================================

Background thread that polls ``/api/health`` so the status bar always knows
whether the Python backend is reachable.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from ui_tui.core.state import TUIState

#: How often to poll (seconds).
POLL_INTERVAL = 5.0

#: Backend URL — can be overridden via FORGE_BACKEND env var.
DEFAULT_BACKEND = "http://localhost:8000"


class ServerHealthPoller:
    """Polls /api/health in a background thread and updates ``state.server_up``."""

    def __init__(
        self,
        state: TUIState,
        on_change: Optional[Callable[[bool], None]] = None,
        backend_url: str = DEFAULT_BACKEND,
    ) -> None:
        self.state = state
        self.on_change = on_change
        self.backend_url = backend_url
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _poll_once(self) -> None:
        import urllib.request

        url = f"{self.backend_url}/api/health"
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                up = resp.status == 200
        except Exception:
            up = False

        if up != self.state.server_up:
            self.state.server_up = up
            if self.on_change:
                self.on_change(up)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._loop, name="forge-health-poller", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._poll_once()
            time.sleep(POLL_INTERVAL)


__all__ = ["ServerHealthPoller"]
