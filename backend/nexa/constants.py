"""
Nexa Agent — Constants
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import os
from pathlib import Path

NEXA_NAME = "Nexa Agent"
NEXA_SHORT = "Nexa"
NEXA_VERSION = "1.0.0"
NEXA_AUTHOR = "Dearly Febriano Irwansyah"
NEXA_LICENSE = "MIT"
NEXA_TAGLINE = "The advanced AI agent by Dearly Febriano Irwansyah"

# Home directory for Nexa runtime artifacts.
NEXA_HOME = Path(os.environ.get("NEXA_HOME", Path.home() / ".nexa"))
NEXA_PROFILE = os.environ.get("NEXA_PROFILE", "default")

# Subdirectories.
NEXA_DIRS = {
    "sessions": NEXA_HOME / "sessions",
    "skills": NEXA_HOME / "skills",
    "memory": NEXA_HOME / "memory",
    "logs": NEXA_HOME / "logs",
}

# Memory files.
NEXA_MEMORY_FILES = {
    "memory": "MEMORY.md",
    "user": "USER.md",
}

# Conversation loop safeguards.
NEXA_MAX_TOOL_ITERATIONS = 8
NEXA_MAX_CONTEXT_MESSAGES = 30

# Default model.
NEXA_DEFAULT_MODEL = os.environ.get("NEXA_MODEL", "gpt-4o")

# Provider env vars.
NEXA_API_KEY = os.environ.get("NEXA_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
NEXA_BASE_URL = os.environ.get("NEXA_BASE_URL", "")

# Workspace for file/terminal tools.
NEXA_WORKSPACE = Path(os.environ.get("NEXA_WORKSPACE", Path.cwd() / "nexa-workspace"))


def ensure_nexa_home() -> None:
    """Ensure ~/.nexa/ and subdirectories exist."""
    for d in NEXA_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)
    NEXA_WORKSPACE.mkdir(parents=True, exist_ok=True)
