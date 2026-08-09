"""
OpenForge — Error Memory
=========================

A persistent log of errors the agent has encountered, indexed by their
healer category. The error memory lets the agent **avoid repeating the
same mistake** — when the same error signature recurs, the memory
returns the previous remediation so the agent can apply it instantly
instead of re-diagnosing from scratch.

Storage: a single JSON file under ``~/.openforge/memory/errors.json``.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_ERROR_RECORDS: int = 200


@dataclass
class ErrorRecord:
    """
    A stored error with its remediation.

    Attributes:
        signature:   Coarse signature (used for matching).
        category:    Healer category (e.g. ``"network"``).
        message:     Original error message (truncated).
        remediation: What fixed it (or what was tried).
        occurrences: Number of times seen.
        first_seen:  Unix timestamp.
        last_seen:   Unix timestamp.
        resolved:    Whether the remediation succeeded.
    """

    signature: str
    category: str
    message: str
    remediation: str = ""
    occurrences: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)


def make_signature(text: str) -> str:
    """
    Produce a coarse signature for repetition matching.

    Strips numbers and file paths so the same logical error in different
    files/lines maps to the same signature.
    """
    norm = re.sub(r"\d+", "N", text)
    norm = re.sub(r"['\"]?[\w./\\-]+\.\w+['\"]?", "PATH", norm)
    return norm.strip().lower()[:200]


class ErrorMemory:
    """
    Persistent error log keyed by signature.

    Load on init, mutate in-memory, :meth:`save` to persist.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """
        Initialize the memory.

        Args:
            path: Path to the JSON file (default ``~/.openforge/memory/errors.json``).
        """
        self.path: Path = path or (
            Path(os.environ.get("FORGE_HOME", Path.home() / ".nexa"))
            / "memory"
            / "errors.json"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, ErrorRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for sig, rec in data.items():
                self._records[sig] = ErrorRecord(**rec)
        except (json.JSONDecodeError, OSError, TypeError):
            self._records = {}

    def save(self) -> None:
        """Persist the memory to disk."""
        # Trim to most-recent MAX_ERROR_RECORDS.
        sorted_recs = sorted(
            self._records.values(),
            key=lambda r: r.last_seen,
            reverse=True,
        )[:MAX_ERROR_RECORDS]
        out = {r.signature: r.to_dict() for r in sorted_recs}
        self.path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def record(
        self,
        error: Any,
        category: str,
        remediation: str = "",
        resolved: bool = False,
    ) -> ErrorRecord:
        """
        Record an error (or reinforce an existing one).

        Args:
            error:       The error (exception or string).
            category:    Healer category.
            remediation: What remediation was applied.
            resolved:    Whether the remediation worked.

        Returns:
            The stored :class:`ErrorRecord`.
        """
        msg = str(error)[:300]
        sig = make_signature(msg)
        now = time.time()
        existing = self._records.get(sig)
        if existing:
            existing.occurrences += 1
            existing.last_seen = now
            if remediation:
                existing.remediation = remediation
            if resolved:
                existing.resolved = True
            return existing
        rec = ErrorRecord(
            signature=sig,
            category=category,
            message=msg,
            remediation=remediation,
            resolved=resolved,
            first_seen=now,
            last_seen=now,
        )
        self._records[sig] = rec
        return rec

    def lookup(self, error: Any) -> Optional[ErrorRecord]:
        """
        Find a previously-recorded error matching ``error``.

        Args:
            error: The error to look up.

        Returns:
            The matching :class:`ErrorRecord`, or ``None`` if unseen.
        """
        sig = make_signature(str(error)[:300])
        return self._records.get(sig)

    def list_unresolved(self) -> List[ErrorRecord]:
        """Return all unresolved error records (most recent first)."""
        return sorted(
            (r for r in self._records.values() if not r.resolved),
            key=lambda r: r.last_seen,
            reverse=True,
        )

    def stats(self) -> Dict[str, Any]:
        """Return a serializable summary."""
        by_cat: Dict[str, int] = {}
        for r in self._records.values():
            by_cat[r.category] = by_cat.get(r.category, 0) + 1
        return {
            "total": len(self._records),
            "unresolved": sum(1 for r in self._records.values() if not r.resolved),
            "by_category": by_cat,
        }
