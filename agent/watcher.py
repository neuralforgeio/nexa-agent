"""S-04: File-watcher with auto-heal — detect syntax/test errors and fix via LLM.

Watches paths (default: current workspace) and, on a change, runs a cheap
linter. When a failure is detected it emits a heal plan by calling a delegate
tool. Implementation is intentionally conservative: no writes without the
delegate's approval.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Optional

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  # pragma: no cover
    Observer = None  # type: ignore[assignment]
    FileSystemEventHandler = object  # type: ignore[misc,assignment]


class _HealHandler(FileSystemEventHandler):
    def __init__(self, heal: Callable[[str], Awaitable[bool]]) -> None:
        self.heal = heal
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    def on_modified(self, event):  # noqa: ANN001
        if not event.is_directory and event.src_path.endswith((".py", ".md", ".json")):
            self.queue.put_nowait(event.src_path)


class Watcher:
    """Minimal watchdog wrapper exposing an async iterator of file paths."""

    def __init__(self, paths: Iterable[str], heal_fn: Callable[[str], Awaitable[bool]]) -> None:
        self.paths = [Path(p) for p in paths]
        self.heal_fn = heal_fn

    def changes(self) -> "async queue of modified file paths":
        if Observer is None:
            raise NotImplementedError("file watcher requires 'watchdog' (pip install watchdog)")
        handler = _HealHandler(self.heal_fn)
        obs = Observer()
        for p in self.paths:
            obs.schedule(handler, str(p), recursive=True)
        obs.start()
        return handler.queue
