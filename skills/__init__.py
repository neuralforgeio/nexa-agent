"""
Nexa Agent — Skills package (v4.4.0)
====================================

Public surface of the Batch 8 skills system. Importing this package discovers
every valid skill manifest under ``skills/<category>/<skill>/`` and re-exports
the registry helpers so callers only need::

    import skills
    await skills.execute_skill("code_review", {...}, provider)

The heavy lifting lives in :mod:`skills.registry` — this module is a thin,
stable facade so internal refactors never break callers.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from .registry import (
    Manifest,
    Skill,
    SkillDisabledError,
    SkillError,
    SkillInputError,
    SkillManifestError,
    SkillNotFoundError,
    SkillOutputError,
    discover_skills,
    execute_skill,
    get_skill,
    is_enabled,
    list_skills,
    load_registry,
    parse_manifest,
    refresh_registry,
    validate_schema,
)

__all__ = [
    "Manifest",
    "Skill",
    "SkillDisabledError",
    "SkillError",
    "SkillInputError",
    "SkillManifestError",
    "SkillNotFoundError",
    "SkillOutputError",
    "discover_skills",
    "execute_skill",
    "get_skill",
    "is_enabled",
    "list_skills",
    "load_registry",
    "parse_manifest",
    "refresh_registry",
    "validate_schema",
]
