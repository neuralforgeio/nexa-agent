"""Tamper-evident audit log.

Each entry is `hash(prev_hash + canonical(entry))`. The chain head is stored
so any modification to history breaks verification downstream.
"""
from __future__ import annotations

import hashlib, json, os
from typing import Any, Dict, List

from openforge.config import FORGE_HOME

_PATH = FORGE_HOME / "audit.log"
_STATE = FORGE_HOME / "audit.state"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        FORGE_HOME.mkdir(parents=True, exist_ok=True)
        if not _STATE.exists():
            _STATE.write_text(_sha(b"nexa-genesis"), encoding="utf-8")

    @property
    def head(self) -> str:
        return _STATE.read_text(encoding="utf-8").strip()

    def append(self, actor: str, action: str, payload: Dict[str, Any]) -> str:
        entry = {"actor": actor, "action": action, "payload": payload, "prev": self.head}
        blob = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
        h = _sha(blob)
        with _PATH.open("a", encoding="utf-8") as f:
            f.write(h + " " + blob.decode("utf-8") + "\n")
        _STATE.write_text(h, encoding="utf-8")
        return h

    def verify(self) -> bool:
        if not _PATH.exists():
            return True
        prev = _sha(b"nexa-genesis")
        for line in _PATH.read_text(encoding="utf-8").splitlines():
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
