"""Backward-compatibility shim for the legacy ``nexa`` package name (v5.x).

OpenForge was renamed from ``nexa`` -> ``openforge``. Older integrations, scripts, and
docs still reference the ``nexa`` import path. This shim re-exports the public symbols
from ``openforge`` so those integrations keep working while emitting a
DeprecationWarning. Prefer importing from ``openforge`` directly in new code.

This module intentionally stays minimal (no logic) — it is a pure alias surface.
"""
from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "The 'nexa' package is deprecated; import from 'openforge' instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    # Re-export the primary version + identity surface if available.
    from openforge.config import FORGE_HOME, FORGE_VERSION, FORGE_WORKSPACE  # noqa: F401
except Exception:  # pragma: no cover - defensive: partial/degraded installs
    FORGE_VERSION = "unknown"  # type: ignore[assignment]

__all__ = ["FORGE_HOME", "FORGE_VERSION", "FORGE_WORKSPACE"]
