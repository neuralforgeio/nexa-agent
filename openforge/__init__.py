"""
Nexa Agent — Core Package
=========================

This package contains the core runtime modules for Nexa Agent:

    - :mod:`nexa.bootstrap`   — UTF-8 stdio setup (imported first).
    - :mod:`nexa.constants`   — Brand identity, version, paths, safeguards.
    - :mod:`nexa.config`      — Environment variable loading.
    - :mod:`nexa.state`       — SQLite + FTS5 persistence layer.
    - :mod:`nexa.provider`    — LLM provider (AsyncOpenAI, streaming, tools).

Entry points (``cli.py``, ``run_agent.py``, ``server.py``) live at the
repository root and import from this package.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

# Import bootstrap first to ensure UTF-8 stdio on all platforms.
from . import bootstrap  # noqa: F401

from .constants import (
    NEXA_AUTHOR,
    FORGE_HOME,
    FORGE_MAX_CONTEXT_MESSAGES,
    FORGE_MAX_TOOL_ITERATIONS,
    NEXA_MODEL,
    NEXA_NAME,
    NEXA_TAGLINE,
    NEXA_VERSION,
    FORGE_WORKSPACE,
    ensure_nexa_home,
)

__all__ = [
    "NEXA_NAME",
    "NEXA_VERSION",
    "NEXA_AUTHOR",
    "NEXA_TAGLINE",
    "FORGE_HOME",
    "FORGE_WORKSPACE",
    "NEXA_MODEL",
    "FORGE_MAX_TOOL_ITERATIONS",
    "FORGE_MAX_CONTEXT_MESSAGES",
    "ensure_nexa_home",
]

__version__ = NEXA_VERSION
