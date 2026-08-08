"""Persistent state for AdaptivePersona + SelfImprovementLoop (I-01/I-02).

Serializes JSON to ``~/.openforge/intelligence_state.json``. Safe to call whether
the module state is present or not; `load()` returns defaults when missing.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from openforge.config import FORGE_HOME

_PATH = FORGE_HOME / "intelligence_state.json"


def save_intelligence(state: Dict[str, Any]) -> None:
    FORGE_HOME.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def load_intelligence() -> Dict[str, Any]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
