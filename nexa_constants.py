"""
Nexa Agent — Constants
======================

Central registry of brand identity, version, and runtime constants.
This is the single source of truth for all Nexa Agent constants
(mirrors Hermes Agent's ``hermes_constants.py``).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

# Re-export everything from config so both `from nexa_constants import ...`
# and `from config import ...` work identically.
from config import (  # noqa: F401
    NEXA_AUTHOR,
    NEXA_HOME,
    NEXA_MAX_CONTEXT_MESSAGES,
    NEXA_MAX_TOOL_ITERATIONS,
    NEXA_MODEL,
    NEXA_NAME,
    NEXA_TAGLINE,
    NEXA_VERSION,
    NEXA_WORKSPACE,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    ensure_nexa_home,
)

__all__ = [
    "NEXA_NAME",
    "NEXA_VERSION",
    "NEXA_AUTHOR",
    "NEXA_TAGLINE",
    "NEXA_HOME",
    "NEXA_WORKSPACE",
    "NEXA_MODEL",
    "NEXA_MAX_TOOL_ITERATIONS",
    "NEXA_MAX_CONTEXT_MESSAGES",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ensure_nexa_home",
]
