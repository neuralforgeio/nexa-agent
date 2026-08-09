"""
Skill: bug_diagnosis
====================

Diagnose a bug from a stack trace (the primary input) plus optional context
files from the workspace. Returns the root cause, the affected files, a
concrete fix suggestion, and a confidence score between 0 and 1.

Permissions used:
  * ``filesystem:workspace`` — each path in ``context_files`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``. No file is needed when only a ``stack_trace`` is
    supplied.
  * ``memory:read`` — declared by the manifest; this handler does not itself
    consult long-term memory.

Honesty note: the root cause, affected files, fix suggestion, and confidence
all come from the model's reply to a prompt that embeds the *actual* stack
trace plus the *actual* contents of any context files read from disk —
nothing here is stubbed or pre-canned. When no context files are given, the
diagnosis is honestly limited to whatever the stack trace itself reveals.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent import tool_api
from skills._common import (
    as_list,
    ask_llm_json,
    coerce_number,
    coerce_str,
    require,
)
from skills.registry import SkillInputError, SkillOutputError

__all__ = ["handle"]

SYSTEM = (
    "You are Forge's bug-diagnosis engine. You are given a REAL stack trace "
    "and, optionally, the REAL contents of related source files. Diagnose "
    "only from the evidence actually shown — never invent files, line "
    "numbers, or causes that the trace and context do not support. Respond "
    "with a SINGLE JSON object, and nothing else (no markdown fences, no "
    "prose around it), with exactly these keys:\n"
    '  "root_cause": a string explaining the most likely root cause.\n'
    '  "affected_files": an array of strings naming the files implicated by '
    "the stack trace / context (empty array if none can be identified).\n"
    '  "fix_suggestion": a string with a concrete, actionable fix.\n'
    '  "confidence": a number between 0 and 1 expressing how confident you '
    "are in this diagnosis given the evidence provided."
)


def _read_context_file(rel_path: str) -> str:
    """Read a context file from the workspace, raising on missing files."""
    try:
        p = tool_api.workspace_path(rel_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid context file path {rel_path!r}: {exc}") from exc
    if not p.exists() or not p.is_file():
        raise SkillInputError(
            f"context file {rel_path!r} does not exist in the workspace "
            f"(resolved to {p})"
        )
    return p.read_text(encoding="utf-8", errors="replace")


async def handle(input_data: dict, provider) -> dict:
    """Diagnose a bug from a stack trace plus optional context files."""
    stack_trace = require(input_data, "stack_trace", str, "the stack trace text")
    if not stack_trace.strip():
        raise SkillInputError("field 'stack_trace' must not be empty")

    raw_context = input_data.get("context_files")
    context_paths: List[str] = []
    for entry in as_list(raw_context):
        if not isinstance(entry, str):
            raise SkillInputError(
                f"field 'context_files' entries must be str, "
                f"got {type(entry).__name__}"
            )
        context_paths.append(entry)

    context_sections: List[str] = []
    for rel in context_paths:
        text = _read_context_file(rel)
        context_sections.append(
            f"CONTEXT FILE: {rel}\n-----\n{text}\n-----"
        )
    context_blob = "\n\n".join(context_sections) if context_sections else "(none provided)"

    prompt = (
        "STACK TRACE (verbatim):\n"
        f"-----\n{stack_trace}\n-----\n\n"
        f"CONTEXT FILES (verbatim, read from the workspace):\n{context_blob}\n\n"
        "Diagnose the failure. Return a single JSON object with keys "
        '"root_cause" (string), "affected_files" (array of strings), '
        '"fix_suggestion" (string), and "confidence" (number 0-1), based '
        "ONLY on the evidence shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    root_cause = coerce_str(data.get("root_cause"), default="")
    if not root_cause.strip():
        # The model returned junk (no usable diagnosis). We refuse to
        # fabricate a root cause — fail loudly instead.
        raise SkillOutputError(
            "bug_diagnosis: model reply contained no usable 'root_cause'"
        )

    confidence = coerce_number(data.get("confidence"), default=0.0)
    confidence = max(0.0, min(1.0, confidence))

    return {
        "root_cause": root_cause,
        "affected_files": [
            coerce_str(item) for item in as_list(data.get("affected_files"))
        ],
        "fix_suggestion": coerce_str(data.get("fix_suggestion"), default=""),
        "confidence": confidence,
    }
