"""Submodule shim for the legacy ``nexa.config`` import path (v5.1.2).

Re-exports the public configuration surface from :mod:`openforge.config` so that
existing ``from nexa.config import ...`` statements keep working. Emits a
DeprecationWarning directing callers to ``openforge.config``.
"""
from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "The 'nexa.config' module is deprecated; import from 'openforge.config' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from openforge.config import *  # noqa: F401,F403 - intentional compat re-export

__all__ = [name for name in dir() if name.isupper()]
