"""OpenForge — Core Package
=========================

This package contains the core runtime modules for OpenForge:

    - :mod:`openforge.bootstrap`   — UTF-8 stdio setup (imported first).
    - :mod:`openforge.constants`   — Brand identity, version, paths, safeguards.
    - :mod:`openforge.config`      — Environment variable loading.
    - :mod:`openforge.state`       — SQLite + FTS5 persistence layer.
    - :mod:`openforge.provider`    — LLM provider (AsyncOpenAI, streaming, tools).

Entry points (``openforge``, ``openforge-chat``, …) come from console_scripts
and import from here.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from . import bootstrap  # noqa: F401

from .constants import (
    FORGE_AUTHOR,
    FORGE_HOME,
    FORGE_MAX_CONTEXT_MESSAGES,
    FORGE_MAX_TOOL_ITERATIONS,
    FORGE_MODEL,
    FORGE_NAME,
    FORGE_TAGLINE,
    FORGE_VERSION,
    FORGE_WORKSPACE,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    ensure_forge_home,
)

# Build __all__ from FORGE_* first; keep FORGE_* as deprecated aliases from
# openforge.config so importing legacy names still works during transition.
from .config import (  # noqa: F401
    FORGE_AUTHOR,
    FORGE_MODEL,
    FORGE_NAME,
    FORGE_TAGLINE,
    FORGE_VERSION,
    ensure_nexa_home,
)

__all__ = [
    "FORGE_NAME",
    "FORGE_VERSION",
    "FORGE_AUTHOR",
    "FORGE_TAGLINE",
    "FORGE_HOME",
    "FORGE_WORKSPACE",
    "FORGE_MODEL",
    "FORGE_MAX_TOOL_ITERATIONS",
    "FORGE_MAX_CONTEXT_MESSAGES",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ensure_forge_home",
    # legacy aliases
    "FORGE_NAME",
    "FORGE_VERSION",
    "FORGE_AUTHOR",
    "FORGE_TAGLINE",
    "FORGE_MODEL",
    "ensure_nexa_home",
]

__version__ = FORGE_VERSION
