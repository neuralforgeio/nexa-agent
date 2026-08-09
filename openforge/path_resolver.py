"""OpenForge — Path Resolver (single source of truth).

Every module in OpenForge MUST resolve runtime paths through this module.
It centralizes the FORGE_HOME / FORGE_LIB / FORGE_WORKSPACE / … layout so
the rest of the codebase never hardcodes a path.
FORGE_* env vars are still honored for one MINOR cycle (backward compat).

Spec (unified):
  FORGE_HOME      default:  ~/.openforge
  FORGE_LIB       read-only core at ~/.openforge/lib
  FORGE_WORKSPACE user workspace at ~/.openforge/workspace
  FORGE_MEMORY    ~/.openforge/memory
  FORGE_SECRETS   ~/.openforge/secrets
  FORGE_SESSIONS  ~/.openforge/sessions
  FORGE_TOOLS_USER ~/.openforge/tools
  FORGE_EXTENSIONS ~/.openforge/extensions
  FORGE_LOGS      ~/.openforge/logs
  FORGE_CACHE     ~/.openforge/cache
  FORGE_PERMISSIONS ~/.openforge/.permissions
  FORGE_VERSIONS  ~/.openforge/.versions
  FORGE_BACKUPS   ~/.openforge/.backups
  FORGE_DB        ~/.openforge/openforge.db

Raises no errors at import time — everything resolves lazily.
"""
from __future__ import annotations

import os
from pathlib import Path

# Tier 1: root ----------------------------------------------------------------
def get_forge_home() -> Path:
    """Return the OpenForge home directory.

    Honours FORGE_HOME, falls back to legacy FORGE_HOME, then uses
    the new default ~/.openforge.
    """
    env = os.environ.get("FORGE_HOME") or os.environ.get("NEXA_HOME")
    return Path(env).expanduser().resolve() if env else Path.home() / ".openforge"


def get_forge_lib() -> Path:
    """Return the read-only core library directory."""
    env = os.environ.get("FORGE_LIB") or os.environ.get("NEXA_LIB")
    return Path(env).expanduser().resolve() if env else get_forge_home() / "lib"


def get_forge_workspace() -> Path:
    """Return the user workspace for writes/scratch."""
    env = os.environ.get("FORGE_WORKSPACE") or os.environ.get("FORGE_WORKSPACE")
    return Path(env).expanduser().resolve() if env else get_forge_home() / "workspace"


def get_forge_memory(filename: str = "") -> Path:
    base = get_forge_home() / "memory"
    return (base / filename).resolve() if filename else base


def get_forge_secrets(filename: str = "") -> Path:
    base = get_forge_home() / "secrets"
    return (base / filename).resolve() if filename else base


def get_forge_sessions() -> Path:
    return get_forge_home() / "sessions"


def get_forge_tools_user() -> Path:
    return get_forge_home() / "tools"


def get_forge_extensions() -> Path:
    return get_forge_home() / "extensions"


def get_forge_logs(filename: str = "") -> Path:
    base = get_forge_home() / "logs"
    return (base / filename).resolve() if filename else base


def get_forge_cache(sub: str = "") -> Path:
    base = get_forge_home() / "cache"
    return (base / sub).resolve() if sub else base


def get_forge_permissions() -> Path:
    return get_forge_home() / ".permissions"


def get_forge_versions() -> Path:
    return get_forge_home() / ".versions"


def get_forge_backups() -> Path:
    return get_forge_home() / ".backups"


def get_forge_db() -> Path:
    return get_forge_home() / "openforge.db"


# Tier 2: classification -------------------------------------------------------
def is_core_path(path: Path | str) -> bool:
    """Return True if *path* lies inside the read-only FORGE_LIB core."""
    try:
        p = Path(path).expanduser().resolve()
    except Exception:
        return False
    try:
        p.relative_to(get_forge_lib())
        return True
    except ValueError:
        return False


def is_workspace_path(path: Path | str) -> bool:
    """Return True if *path* lies inside the user workspace."""
    try:
        Path(path).expanduser().resolve().relative_to(get_forge_workspace())
        return True
    except ValueError:
        return False


__all__ = [
    "get_forge_home",
    "get_forge_lib",
    "get_forge_workspace",
    "get_forge_memory",
    "get_forge_secrets",
    "get_forge_sessions",
    "get_forge_tools_user",
    "get_forge_extensions",
    "get_forge_logs",
    "get_forge_cache",
    "get_forge_permissions",
    "get_forge_versions",
    "get_forge_backups",
    "get_forge_db",
    "is_core_path",
    "is_workspace_path",
]
