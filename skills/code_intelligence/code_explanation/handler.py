"""
Skill: code_explanation
========================

Explain what a source file inside the workspace does, at a ``brief``,
``detailed``, or ``eli5`` level. Returns a prose explanation, the
step-by-step flow of the code, and the file's key dependencies.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``.

Honesty note: the explanation, flow steps, and dependencies come from the
model's reply to a prompt that embeds the *actual* file contents read from
disk — nothing here is stubbed or pre-canned. Quality therefore depends on
both the model and on the file that was really read; a truncated, minified,
or misleading file yields a faithfully limited explanation.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_str, require
from skills.registry import SkillInputError, SkillOutputError

__all__ = ["handle"]

_DETAIL_GUIDANCE: Dict[str, str] = {
    "brief": (
        "2-4 sentences covering only the file's purpose and its main "
        "entry points. No line-by-line walkthrough."
    ),
    "detailed": (
        "A thorough walkthrough: purpose, each function/class, important "
        "control flow, data structures, and notable edge cases."
    ),
    "eli5": (
        "Explain like the reader is five years old: simple words, a small "
        "everyday analogy, no jargon, short sentences."
    ),
}

SYSTEM = (
    "You are Nexa's code-explanation engine. You are given the REAL contents "
    "of a source file plus a requested detail level. Analyse only what is "
    "actually in the file — never invent identifiers, functions, or behaviour "
    "that are not present. Respond with a SINGLE JSON object, and nothing "
    "else (no markdown fences, no prose around it), with exactly these keys:\n"
    '  "explanation": a string explaining what the file does, written at the '
    "requested detail level.\n"
    '  "flow_steps": an array of short strings describing the code\'s '
    "step-by-step flow in execution order.\n"
    '  "dependencies": an array of short strings naming the file\'s key '
    "dependencies (imports, modules, external services). Use an empty array "
    "if there are none."
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


async def handle(input_data: dict, provider) -> dict:
    """Explain a workspace source file at the requested detail level."""
    file_path = require(input_data, "file_path", str, "path to the source file")
    detail_level = require(
        input_data, "detail_level", str, "brief | detailed | eli5"
    )
    if detail_level not in _DETAIL_GUIDANCE:
        raise SkillInputError(
            f"detail_level must be one of {sorted(_DETAIL_GUIDANCE)}, "
            f"got {detail_level!r}"
        )

    content = _read_workspace_file(file_path)
    guidance = _DETAIL_GUIDANCE[detail_level]

    prompt = (
        f"File: {file_path}\n"
        f"Detail level: {detail_level}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Write the explanation at the '{detail_level}' level: {guidance}\n\n"
        'Return a single JSON object with keys "explanation" (string), '
        '"flow_steps" (array of strings), and "dependencies" (array of '
        "strings), describing ONLY the file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise to the manifest's output_schema so the executor's output
    # validation always sees well-typed values, regardless of how chatty or
    # sparse the model's raw reply was.
    explanation = coerce_str(data.get("explanation"), default="")
    if not explanation.strip():
        # The model returned junk (no usable explanation). We refuse to
        # fabricate one from nothing — fail loudly instead so the executor's
        # output contract is never satisfied with an empty payload.
        raise SkillOutputError(
            "code_explanation: model reply contained no usable 'explanation'"
        )
    return {
        "explanation": explanation,
        "flow_steps": [coerce_str(step) for step in as_list(data.get("flow_steps"))],
        "dependencies": [coerce_str(dep) for dep in as_list(data.get("dependencies"))],
    }
