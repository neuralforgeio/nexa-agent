"""Tamper-evident audit log.

Each entry is `hash(prev_hash + canonical(entry))`. The chain head is stored
so any modification to history breaks verification downstream.
"""
from __future__ import annotations

import hashlib, json, os
from pathlib import Path
from typing import Any, Dict, List


def _forge_home() -> Path:
    """Resolve FORGE_HOME at call time (fresh env read).

    Modules may read the env var at import time; we DEFER it so test suites
    can temporarily patch to a sandbox without breaking the writer.
    """
    return Path(os.environ.get("FORGE_HOME") or os.environ.get("NEXA_HOME") or str(Path.home() / ".openforge"))


def _path_log() -> Path:
    return _forge_home() / "audit.log"


def _path_state() -> Path:
    return _forge_home() / "audit.state"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        _forge_home().mkdir(parents=True, exist_ok=True)
        state = _path_state()
        if not state.exists():
            state.write_text(_sha(b"forge-genesis"), encoding="utf-8")

    @property
    def head(self) -> str:
        return _path_state().read_text(encoding="utf-8").strip()

    def append(self, actor: str, action: str, payload: Dict[str, Any]) -> str:
        entry = {"actor": actor, "action": action, "payload": payload, "prev": self.head}
        blob = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
        h = _sha(blob)
        with _path_log().open("a", encoding="utf-8") as f:
            f.write(h + " " + blob.decode("utf-8") + "\n")
        _path_state().write_text(h, encoding="utf-8")
        return h

    def verify(self) -> bool:
        log = _path_log()
        if not log.exists():
            return True
        prev = _sha(b"forge-genesis")
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            h, blob = line.split(" ", 1)
            if _sha(blob.encode("utf-8")) != h:
                return False
            entry = json.loads(blob)
            if entry.get("prev") != prev:
                return False
            prev = h
        return prev == self.head
