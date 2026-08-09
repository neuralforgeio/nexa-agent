"""
Skill: migration_assistance
===========================

Plan the migration of a workspace file from one framework / language /
library version to another (``from`` -> ``to``, e.g. ``flask 2.x`` ->
``fastapi``, or ``python 2.7`` -> ``python 3.11``). Returns ordered migration
steps — each with a step number, a description, and a concrete code change —
plus a list of breaking changes to watch for after migrating.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``.
  * ``memory:read`` — declared by the manifest; this handler itself does not
    touch memory.

Honesty note: every entry in ``migration_steps`` and ``breaking_changes``
comes from the model's reply to a prompt that embeds the *actual* file
contents read from disk together with the real ``from``/``to`` versions —
nothing here is stubbed, template-generated, or pre-canned. If the model's
reply is not parseable JSON, ``ValueError`` propagates rather than
fabricating a migration plan; LLM errors propagate as ``RuntimeError``.
Plan quality therefore depends on both the model and the real file.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]

SYSTEM = (
    "You are Forge's migration-planning engine. You are given the REAL "
    "contents of a single source file plus a migration FROM a named "
    "framework/language/library version TO another. Produce a practical, "
    "ordered migration plan grounded in the code actually shown: reference "
    "the real functions, classes, imports, and patterns in that file when "
    "describing each step, and show concrete code changes that transform "
    "that real code. Never invent identifiers or file contents. Respond "
    "with a SINGLE JSON object, and nothing else (no markdown fences, no "
    "prose around it), with exactly these keys:\n"
    '  "migration_steps": an array of objects, each with keys "step" '
    "(integer, 1-based, in execution order), \"description\" (what to do, "
    "referencing the real code), and \"code_change\" (the concrete "
    "replacement code or edit for this step).\n"
    '  "breaking_changes": an array of strings listing behaviours/APIs in '
    "the FROM version that change or disappear in the TO version and that "
    "this file relies on."
)


def _read_workspace_file(file_path: str) -> str:
    """Resolve ``file_path`` inside the workspace and read it as UTF-8 text."""
    try:
        p = tool_api.workspace_path(file_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid file_path {file_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"file {file_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )
    return p.read_text(encoding="utf-8", errors="replace")


def _coerce_step_number(value: Any, fallback: int) -> int:
    """Best-effort positive int for a step number; never raises."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value > 0 else fallback
    if isinstance(value, float):
        n = int(value)
        return n if n > 0 else fallback
    if isinstance(value, str):
        try:
            n = int(float(value.strip()))
            return n if n > 0 else fallback
        except ValueError:
            return fallback
    return fallback


def _stringify_code_change(value: Any) -> str:
    """Coerce a model-supplied code change (dict/list ok) into a string."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _normalise_step(item: Any, fallback_number: int) -> Dict[str, Any]:
    """Map a raw model step to the manifest's per-step schema."""
    if isinstance(item, dict):
        return {
            "step": _coerce_step_number(item.get("step"), fallback_number),
            "description": coerce_str(item.get("description")),
            "code_change": _stringify_code_change(item.get("code_change")),
        }
    # Non-object step (e.g. a bare string): keep the content as description.
    return {
        "step": fallback_number,
        "description": coerce_str(item),
        "code_change": "",
    }


async def handle(input_data: dict, provider) -> dict:
    """Plan the migration of a workspace file from ``from`` to ``to``."""
    file_path = require(input_data, "file_path", str, "path to the file to migrate")
    from_version = require(
        input_data, "from", str, "source framework/version (e.g. 'flask 2.x')"
    )
    to_version = require(
        input_data, "to", str, "target framework/version (e.g. 'fastapi')"
    )

    content = _read_workspace_file(file_path)

    prompt = (
        f"File: {file_path}\n"
        f"Migrate FROM: {from_version}\n"
        f"Migrate TO: {to_version}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Produce an ordered migration plan to take the file above from "
        f"{from_version} to {to_version}. Each step must reference the real "
        "code shown and include a concrete code_change. Also list the "
        "breaking changes between those versions that this specific file "
        "relies on.\n\n"
        'Return a single JSON object with keys "migration_steps" (array of '
        'objects with "step" [integer], "description" [string], '
        '"code_change" [string]) and "breaking_changes" (array of strings), '
        "describing ONLY the file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise to the manifest's output_schema so the executor's output
    # validation always sees well-typed values, regardless of how chatty or
    # sparse the model's raw reply was. Content itself (which steps, which
    # code changes) always comes from the model's reply about the real file —
    # only the TYPES are normalised here.
    steps: List[Dict[str, Any]] = [
        _normalise_step(item, i + 1)
        for i, item in enumerate(as_list(data.get("migration_steps")))
    ]
    steps.sort(key=lambda s: s["step"])
    breaking_changes: List[str] = [
        coerce_str(item) for item in as_list(data.get("breaking_changes"))
    ]

    return {
        "migration_steps": steps,
        "breaking_changes": breaking_changes,
    }
