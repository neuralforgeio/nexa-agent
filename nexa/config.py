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


def _read_version_from_pyproject() -> str:
    """
    Read the version from ``pyproject.toml`` so there's a single source of truth.

    Falls back to ``"1.9.0"`` if the file cannot be read (e.g. when the
    package is installed in a non-source layout).

    Returns:
        The version string from ``[project].version`` in pyproject.toml.
    """
    try:
        toml_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        for line in toml_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("version") and "=" in line:
                # e.g. version = "1.9.0"
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "1.9.0"


# ---------------------------------------------------------------------------
# Brand identity
# ---------------------------------------------------------------------------
NEXA_NAME: str = "Nexa Agent"
"""The human-readable product name."""

NEXA_VERSION: str = _read_version_from_pyproject()
"""
The current semantic version of Nexa Agent. Read from ``pyproject.toml``
so there is a single source of truth (no drift between the package
metadata and the runtime banner).
"""

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
