"""
Skill: code_refactoring
========================

Propose automated refactors (``extract_method``, ``rename``, ``simplify``,
or ``all``) for a source file inside the workspace. Returns each candidate
refactor with a type, a description, before/after snippets, and a line
number, plus a boolean ``applied`` flag.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``NEXA_WORKSPACE``.
  * ``filesystem:workspace:write`` — declared in the manifest for future
    opt-in auto-apply; the current handler never writes.

Honesty note: the suggested refactors come from the model's reply to a
prompt that embeds the *actual* file contents read from disk — nothing here
is stubbed or pre-canned. Auto-apply is intentionally conservative: this
handler NEVER rewrites the file on its own. ``applied`` is always ``False``;
applying a suggestion is an explicit, opt-in decision left to the caller
(and a safe-apply path would additionally require the model's ``before``
snippet to match the on-disk content verbatim). Suggestions are advisory
only and must be reviewed before use.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]

_REFACTOR_TYPES = ("extract_method", "rename", "simplify", "all")

SYSTEM = (
    "You are Nexa's code-refactoring engine. You are given the REAL contents "
    "of a source file plus a requested refactor type (extract_method, "
    "rename, simplify, or all). Analyse only what is actually in the file — "
    "never invent identifiers, functions, or code that is not present. "
    "Propose concrete, minimal, behaviour-preserving refactors. Respond with "
    "a SINGLE JSON object, and nothing else (no markdown fences, no prose "
    "around it), with exactly these keys:\n"
    '  "refactors": an array of objects, each with keys:\n'
    '      "type": one of "extract_method", "rename", "simplify".\n'
    '      "description": a short string explaining the refactor and why.\n'
    '      "before": a string with the exact code snippet to be changed, '
    "copied verbatim from the file.\n"
    '      "after": a string with the replacement code.\n'
    '      "line": an integer, the 1-based line number where the "before" '
    "snippet starts.\n"
    '  "applied": a boolean, ALWAYS false — you only suggest refactors, you '
    "never modify the file.\n"
    "If the file needs no refactors of the requested kind, return an empty "
    '"refactors" array.'
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


def _normalise_refactors(raw: Any) -> list:
    """Coerce the model's refactor list into schema-shaped objects."""
    refactors = []
    for item in as_list(raw):
        if not isinstance(item, dict):
            continue
        line = item.get("line")
        if isinstance(line, bool) or not isinstance(line, int):
            try:
                line = int(str(line).strip())
            except (TypeError, ValueError):
                line = 0
        refactors.append(
            {
                "type": coerce_str(item.get("type")),
                "description": coerce_str(item.get("description")),
                "before": coerce_str(item.get("before")),
                "after": coerce_str(item.get("after")),
                "line": line,
            }
        )
    return refactors


async def handle(input_data: dict, provider) -> dict:
    """Suggest refactors for a workspace source file (never auto-applies)."""
    file_path = require(input_data, "file_path", str, "path to the source file")
    refactor_type = require(
        input_data, "refactor_type", str, "extract_method | rename | simplify | all"
    )
    if refactor_type not in _REFACTOR_TYPES:
        raise SkillInputError(
            f"refactor_type must be one of {list(_REFACTOR_TYPES)}, "
            f"got {refactor_type!r}"
        )

    content = _read_workspace_file(file_path)

    prompt = (
        f"File: {file_path}\n"
        f"Refactor type requested: {refactor_type}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Propose {refactor_type} refactors for the file above. For each "
        'candidate, copy the "before" snippet EXACTLY as it appears in the '
        "file and give the 1-based starting line number.\n\n"
        'Return a single JSON object with keys "refactors" (array of '
        '{"type", "description", "before", "after", "line"}) and "applied" '
        "(boolean, always false — suggestions only, the file is NOT "
        "modified)."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Conservative auto-apply policy: we do not rewrite the file here. A
    # future safe-apply must be explicit opt-in AND verify the model's
    # "before" snippet occurs verbatim in the on-disk content before any
    # write. Until then `applied` is honestly reported as False, even if the
    # model claims otherwise.
    return {
        "refactors": _normalise_refactors(data.get("refactors")),
        "applied": False,
    }
