"""OpenForge — Constants
=====================

Single source of truth for OpenForge identity, version, paths, and
runtimeSafety constants.

Imports from :mod:`openforge.config` for FORGE_*; keeps <<<FORGE_*>>> aliases
for one MINOR cycle to avoid breaking third-party imports during migration.

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

# ---------------------------------------------------------------------------
# Legacy aliases — set them AFTER the canonical FORGE_* names exist.
# Keeping these here means any `from openforge.constants import FORGE_NAME`
# continues to work for one MINOR cycle, then we delete them.
# ---------------------------------------------------------------------------
FORGE_NAME = FORGE_NAME
FORGE_VERSION = FORGE_VERSION
FORGE_AUTHOR = FORGE_AUTHOR
FORGE_TAGLINE = FORGE_TAGLINE
FORGE_MODEL = FORGE_MODEL
ensure_nexa_home = ensure_forge_home

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
    # legacy aliases (deprecated, will be removed in v5.x)
    "FORGE_NAME",
    "FORGE_VERSION",
    "FORGE_AUTHOR",
    "FORGE_TAGLINE",
    "FORGE_MODEL",
    "ensure_nexa_home",
]
