"""
OpenForge — Configuration & Constants
======================================

Centralizes all configuration for the OpenForge backend. Loads environment
variables from a `.env` file (if present) and exposes them as module-level
constants.

Environment variables (canonical `FORGE_*`; legacy `FORGE_*` honored):
    FORGE_HOME          — runtime home (default: ~/.openforge)
    FORGE_WORKSPACE     — file/terminal sandbox (default: ~/.openforge/workspace)
    OPENAI_API_KEY      — API key for OpenAI-compatible providers
    OPENAI_BASE_URL     — custom base URL (OpenRouter, llama.cpp, ...)
    FORGE_MODEL         — model identifier (default: gpt-4o)

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

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
FORGE_NAME: str = "OpenForge"
"""The human-readable product name (kept for legacy; use FORGE_NAME in new code)."""

# Canonical constants after the OpenForge rebrand.
FORGE_NAME: str = "OpenForge"
FORGE_AUTHOR: str = "Dearly Febriano Irwansyah"

# v5.0.0 canonical name after the consolidated rebrand: single source of truth.
FORGE_VERSION: str = _read_version_from_pyproject()
FORGE_VERSION: str = FORGE_VERSION  # deprecated alias, kept for one MINOR cycle
"""
The current semantic version of OpenForge. Read from ``pyproject.toml``
so there is a single source of truth (no drift between package metadata and
the runtime banner).
"""

FORGE_AUTHOR: str = FORGE_AUTHOR  # deprecated alias
"""The copyright holder and primary author."""


# ---------------------------------------------------------------------------
# v4.1.6: canonical config.yaml as a secondary, human-editable source of truth
# ---------------------------------------------------------------------------

_FORGE_REPO_META_CACHE: Optional[Dict[str, Any]] = None


def read_repo_meta() -> Dict[str, Any]:
    """
    Read canonical metadata from the repo-root ``config.yaml``.

    The YAML file is the single source of truth for: repository description,
    author URL, license file, frozen-history file list, and hygiene watchlist.
    ``pyproject.toml`` remains the canonical version pin (read by
    :func:`_read_version_from_pyproject`); this complements it.

    Returns:
        A dict with keys like ``project.name``, ``project.creator``,
        ``project.repository``; empty dict if the file is unreadable.
    """
    global _FORGE_REPO_META_CACHE
    if _FORGE_REPO_META_CACHE is not None:
        return _FORGE_REPO_META_CACHE
    try:
        import yaml  # pyyaml from pyproject dependencies
    except ImportError:  # pragma: no cover
        return {}
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        # yaml.safe_load returns None on empty file
        _FORGE_REPO_META_CACHE = dict(raw) if isinstance(raw, dict) else {}
    except Exception:
        _FORGE_REPO_META_CACHE = {}
    return _FORGE_REPO_META_CACHE

FORGE_TAGLINE: str = "Forge intelligent code, locally."
"""A short marketing tagline (deprecated alias; use FORGE_TAGLINE)."""

FORGE_TAGLINE: str = "Forge intelligent code, locally."


# ---------------------------------------------------------------------------
# Runtime paths
# ---------------------------------------------------------------------------
FORGE_HOME: Path = Path(os.environ.get("FORGE_HOME", Path.home() / ".openforge"))
"""
The logical home directory for OpenForge runtime artifacts (sessions, memory,
logs). Defaults to ``~/.openforge/``. Created on first use. Honors FORGE_HOME
or legacy FORGE_HOME (via the resolver) but the default lands on .openforge.
"""

FORGE_WORKSPACE: Path = Path(
    os.environ.get("FORGE_WORKSPACE", Path.cwd() / "forge-workspace")
)
"""
The filesystem sandbox for file & terminal tools. All file operations
are confined here to prevent arbitrary access to the host filesystem.
"""

FORGE_DB_PATH: Path = FORGE_HOME / "openforge.db"
"""The path to the SQLite database used for conversation persistence."""

FORGE_SECRETS_DIR: Path = FORGE_HOME / "secrets"
"""
Directory for storing sensitive credentials (API keys, tokens) separately
from the main ``.env`` file. Files here are created with mode 0o600
(best-effort on Unix). v3.0.0 introduced this as part of the terminal
security hardening — ``run_terminal_command`` blocks access to ``~/.openforge/``
entirely, so credentials live here safely.
"""


def _ensure_secrets_dir() -> None:
    """
    Create :data:`FORGE_SECRETS_DIR` and tighten its permissions.

    On Unix, the directory is set to mode 0o700 (owner-only). On Windows,
    permissions are inherited from the parent — this is best-effort.
    """
    FORGE_SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(FORGE_SECRETS_DIR, 0o700)
        except OSError:
            pass


# Ensure secrets dir exists on import (best-effort).
try:
    _ensure_secrets_dir()
except OSError:
    pass


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

FORGE_MODEL: str = os.environ.get("FORGE_MODEL") or os.environ.get("FORGE_MODEL", "gpt-4o")
"""
The model identifier sent to the provider. Defaults to ``gpt-4o``.
Reads FORGE_MODEL first; falls back to legacy FORGE_MODEL for one MINOR cycle.
"""

FORGE_MODEL: str = FORGE_MODEL
"""Canonical name for the model; mirror of FORGE_MODEL until v5.x."""


# ---------------------------------------------------------------------------
# Agent loop safeguards
# ---------------------------------------------------------------------------
FORGE_MAX_TOOL_ITERATIONS: int = 8
"""
Maximum number of LLM round-trips in a single conversation turn.
Prevents infinite tool-calling loops.
"""

FORGE_MAX_CONTEXT_MESSAGES: int = 30
"""
Maximum number of historical messages carried into the system prompt
window. Older messages are truncated to fit the context budget.
"""


# ---------------------------------------------------------------------------
# Initialization helper
# ---------------------------------------------------------------------------
def ensure_forge_home() -> None:
    """
    Ensure that the ``FORGE_HOME`` directory and its subdirectories exist.

    Creates ``~/.openforge/`` along with ``sessions``, ``memory``, ``logs``
    subdirectories, and the ``FORGE_WORKSPACE`` sandbox directory.

    This function is safe to call multiple times — it uses
    ``parents=True, exist_ok=True``.
    """
    for subdir in ("sessions", "memory", "logs"):
        (FORGE_HOME / subdir).mkdir(parents=True, exist_ok=True)
    FORGE_WORKSPACE.mkdir(parents=True, exist_ok=True)


def ensure_nexa_home() -> None:
    """Deprecated alias for ensure_forge_home()."""
    ensure_forge_home()
