"""Submodule shim for the legacy ``nexa.constants`` import path (v5.1.2).

Re-exports constants (FORGE_NAME, FORGE_VERSION, ...) from :mod:`openforge.constants`.
Emits a DeprecationWarning directing callers to ``openforge.constants``.
"""
from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "The 'nexa.constants' module is deprecated; import from 'openforge.constants' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from openforge.constants import *  # noqa: F401,F403 - intentional compat re-export

__all__ = [name for name in dir() if name.isupper()]
