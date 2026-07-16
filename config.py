"""
Nexa Agent — Configuration & Constants
=======================================

This module centralizes all configuration for the Nexa Agent backend.
It loads environment variables from a ``.env`` file (if present) and
exposes them as module-level constants.

Environment variables:
    OPENAI_API_KEY   — Your OpenAI (or OpenAI-compatible) API key.
    OPENAI_BASE_URL  — Optional custom base URL (e.g. OpenRouter).
    NEXA_MODEL       — The model identifier to use (default: gpt-4o).
    NEXA_HOME        — The runtime home directory (default: ~/.nexa).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from pathlib import Path

# Load environment variables from .env if it exists.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional at import time; the app still works
    # if the variables are set in the shell environment.
    pass


# ---------------------------------------------------------------------------
# Brand identity
# ---------------------------------------------------------------------------
NEXA_NAME: str = "Nexa Agent"
"""The human-readable product name."""

NEXA_VERSION: str = "1.0.0"
"""The current semantic version of Nexa Agent."""

NEXA_AUTHOR: str = "Dearly Febriano Irwansyah"
"""The copyright holder and primary author."""

NEXA_TAGLINE: str = "The advanced AI agent by Dearly Febriano Irwansyah"
"""A short marketing tagline used in prompts and metadata."""


# ---------------------------------------------------------------------------
# Runtime paths
# ---------------------------------------------------------------------------
NEXA_HOME: Path = Path(os.environ.get("NEXA_HOME", Path.home() / ".nexa"))
"""
The logical home directory for Nexa runtime artifacts (sessions, memory,
logs). Defaults to ``~/.nexa/``. Created on first use.
"""

NEXA_WORKSPACE: Path = Path(
    os.environ.get("NEXA_WORKSPACE", Path.cwd() / "nexa-workspace")
)
"""
The filesystem sandbox for file & terminal tools. All file operations
are confined here to prevent arbitrary access to the host filesystem.
"""

NEXA_DB_PATH: Path = NEXA_HOME / "nexa.db"
"""The path to the SQLite database used for conversation persistence."""


# ---------------------------------------------------------------------------
# LLM provider configuration
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
"""
The API key for the LLM provider. Falls back to the ``OPENAI_API_KEY``
environment variable. Required for the agent to function.
"""

OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "")
"""
Optional custom base URL for OpenAI-compatible endpoints (e.g.
``https://openrouter.ai/api/v1``). Empty string means use the default
OpenAI endpoint.
"""

NEXA_MODEL: str = os.environ.get("NEXA_MODEL", "gpt-4o")
"""
The model identifier sent to the provider. Defaults to ``gpt-4o``.
"""


# ---------------------------------------------------------------------------
# Agent loop safeguards
# ---------------------------------------------------------------------------
NEXA_MAX_TOOL_ITERATIONS: int = 8
"""
Maximum number of LLM round-trips in a single conversation turn.
Prevents infinite tool-calling loops.
"""

NEXA_MAX_CONTEXT_MESSAGES: int = 30
"""
Maximum number of historical messages carried into the system prompt
window. Older messages are truncated to fit the context budget.
"""


# ---------------------------------------------------------------------------
# Initialization helper
# ---------------------------------------------------------------------------
def ensure_nexa_home() -> None:
    """
    Ensure that the ``NEXA_HOME`` directory and its subdirectories exist.

    Creates ``~/.nexa/`` along with ``sessions``, ``memory``, ``logs``
    subdirectories, and the ``NEXA_WORKSPACE`` sandbox directory.

    This function is safe to call multiple times — it uses
    ``parents=True, exist_ok=True``.
    """
    for subdir in ("sessions", "memory", "logs"):
        (NEXA_HOME / subdir).mkdir(parents=True, exist_ok=True)
    NEXA_WORKSPACE.mkdir(parents=True, exist_ok=True)
