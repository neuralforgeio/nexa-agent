"""OpenForge — Constants
======================

Central registry of brand identity, version, and runtime constants.
Single source of truth for OpenForge constants.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from .config import (  # noqa: F401
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
    # Backwards-compat aliases (one MINOR cycle).
    "NEXA_NAME",
    "NEXA_VERSION",
    "NEXA_AUTHOR",
    "NEXA_TAGLINE",
    "NEXA_MODEL",
]
