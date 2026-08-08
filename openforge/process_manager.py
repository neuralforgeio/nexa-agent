"""
Nexa Agent — Process Manager (Cross-Platform Process-Safe Singletons)
======================================================================

Guarantees that long-lived Nexa subsystems (the FastAPI web server, the
Next.js dev server, etc.) run **exactly once per user account**, fixing the
"2 processes when I send one message" bug.

How it works
------------
A lock file is created at ``~/.openforge/locks/<name>.lock`` containing the
owning PID. Before trusting the lock, we check whether the recorded PID
is **actually still alive**:

- **Windows** — ``OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, pid)``
  via ``ctypes``. This does not require any third-party packages.
- **POSIX**   — ``os.kill(pid, 0)`` (signal 0 = existence check).

If the recorded PID is dead (the previous process crashed without cleanup),
the lock is treated as *stale* and reclaimed by the new process. If the PID
is alive, :class:`SingletonConflict` is raised with remediation steps.

This means:
- A killed/crashed server never blocks a restart (stale lock auto-recovered).
- A genuinely running duplicate is caught with a clear error message.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

from .config import FORGE_HOME


def _pid_exists(pid: int) -> bool:
    """
    Return whether a process with the given PID is currently running.

    Uses ``ctypes`` on Windows (no psutil dependency) and ``os.kill(pid, 0)``
    on POSIX. Returns ``False`` on any error (defensive — a PID we can't
    verify is treated as dead so a fresh start is never blocked).
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            try:
                # Query exit code: 259 (STILL_ACTIVE) means running.
                exit_code = ctypes.c_ulong()
                ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return bool(ok) and exit_code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class SingletonProcess:
    """
    A process-safe singleton backed by a PID file in ``~/.openforge/locks/``.

    Acquire with :func:`acquire_singleton`; release with :meth:`release` or
    let :meth:`__del__` clean up. The lock file is removed on release so
    subsequent starts are never blocked by stale locks.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: The singleton name (e.g. ``"server"``, ``"web"``).
        """
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        lock_dir = FORGE_HOME / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.path: Path = lock_dir / f"{safe}.lock"
        self.pid_path: Path = lock_dir / f"{safe}.pid"
        self._acquired = False

    # ------------------------------------------------------------------
    def acquire(self, label: str = "") -> "SingletonProcess":
        """
        Acquire the singleton, raising :class:`SingletonConflict` if taken.

        Idempotent: calling :meth:`acquire` on an object that already holds
        the lock returns ``self`` without raising — re-entrant within one
        logical owner.

        If a previous PID file exists but its process is dead, the lock is
        reclaimed silently (stale-lock recovery). Re-acquiring from a
        *different* :class:`SingletonProcess` instance while the lock is
        still held (including re-acquiring in the same process with a
        fresh object) raises :class:`SingletonConflict`, because that
        pattern is exactly the "2 processes" bug we're guarding against.
        """
        if self._acquired:
            # This object already holds the lock — safe re-entry.
            return self

        existing_pid = self._read_pid()
        if existing_pid:
            # Any live owner (even if it's our PID but a *different*
            # SingletonProcess object) means the singleton is taken —
            # that would create two live owners, the exact bug.
            if _pid_exists(existing_pid):
                raise SingletonConflict(
                    f"[nexa] another '{self.name}' process is already running "
                    f"(pid={existing_pid}).\n"
                    f"  Fix with:\n"
                    f"    Windows:  taskkill /PID {existing_pid} /F\n"
                    f"    POSIX:    kill {existing_pid}\n"
                    f"This prevents the double-process bug."
                )
            # Stale lock: previous owner is gone. Reclaim.

        # Write our own PID + label.
        payload = f"pid={os.getpid()}\nlabel={label or self.name}\nts={int(time.time())}\n"
        self.pid_path.write_text(payload, encoding="utf-8")
        # Marker file for existence checks.
        self.path.write_text("1", encoding="utf-8")
        self._acquired = True
        return self

    # ------------------------------------------------------------------
    def release(self) -> None:
        """Release the singleton (best-effort; safe to call twice)."""
        if not self._acquired:
            return
        self._acquired = False
        # Delete stable file FIRST so re-acquisition reads a missing pid file.
        # Order matters: removing .pid before .lock avoids the race where a
        # re-acquirer sees the (stale) .lock but an out-of-date .pid.
        for p in (self.pid_path, self.path):
            try:
                p.unlink(missing_ok=True)  # Python ≥3.8
            except OSError:
                pass

    # ------------------------------------------------------------------
    def _read_pid(self) -> Optional[int]:
        """Read the PID recorded in the pid file, or ``None``."""
        try:
            text = self.pid_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            if line.startswith("pid="):
                try:
                    return int(line[4:])
                except ValueError:
                    return None
        return None

    # ------------------------------------------------------------------
    def __enter__(self) -> "SingletonProcess":
        return self

    def __exit__(self, *_exc) -> None:
        self.release()

    def __del__(self) -> None:  # pragma: no cover - GC safety net
        try:
            self.release()
        except Exception:
            pass


class SingletonConflict(RuntimeError):
    """Raised when a singleton is already held by a live process."""


def acquire_singleton(name: str, label: str = "") -> SingletonProcess:
    """
    Acquire a named singleton, raising :class:`SingletonConflict` if taken.

    Usage::

        from openforge.process_manager import acquire_singleton, SingletonConflict
        try:
            _lock = acquire_singleton("server", label="server.py:8000")
        except SingletonConflict as e:
            print(e); sys.exit(1)

    Args:
        name:  The singleton name (e.g. ``"server"``, ``"web"``).
        label: Optional human-readable label recorded alongside the PID.

    Returns:
        The held :class:`SingletonProcess` — keep it referenced for the
        process lifetime; the lock is released on :meth:`release`, context
        exit, or garbage collection.
    """
    return SingletonProcess(name).acquire(label=label)
