"""
Skill: code_review
==================

Review a workspace file for bugs, security issues, and style violations
(according to the requested ``focus``: ``bugs`` | ``security`` | ``style`` |
``all``). Returns structured findings — each with severity, line number,
message, and a concrete suggestion — plus a human-readable summary.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``NEXA_WORKSPACE``.
  * ``memory:read`` / ``memory:write`` — declared by the manifest; this
    handler itself does not touch memory.

Honesty note: every finding in ``issues`` and the ``summary`` text come from
the model's reply to a prompt that embeds the *actual* file contents read
from disk — nothing here is stubbed, template-generated, or pre-canned. If
the model's reply is not parseable JSON, ``ValueError`` propagates rather
than fabricating findings. Review quality therefore depends on both the
model and on the file that was really read.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_str, require
from skills._common import coerce_number  # noqa: F401  (kept import surface aligned with batch-8 kit)
from skills._llm import chat_json  # noqa: F401  (re-exported seam; ask_llm_json uses it)
from skills.registry import SkillInputError

__all__ = ["handle"]

_FOCUS_VALUES = ("bugs", "security", "style", "all")

SYSTEM = (
    "You are Nexa's code-review engine. You are given the REAL contents of a "
    "single source file plus a review focus (bugs | security | style | all). "
    "Review only what is actually in the file — report issues that genuinely "
    "exist in the shown code and reference the real line numbers where they "
    "occur. Never invent findings, identifiers, or line numbers. Respond "
    "with a SINGLE JSON object, and nothing else (no markdown fences, no "
    "prose around it), with exactly these keys:\n"
    '  "issues": an array of objects, each with keys "severity" (one of '
    '"info" | "low" | "medium" | "high" | "critical"), "line" (integer '
    'line number, 1-based; use 0 if not tied to a specific line), '
    '"message" (what is wrong), and "suggestion" (how to fix it). Use an '
    "empty array if the file has no findings for the requested focus.\n"
    '  "summary": a short string summarising the overall review outcome.'
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


def _coerce_line(value: Any) -> int:
    """Best-effort int for an issue's line number; never raises. Default 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return 0
    return 0


def _normalise_issue(item: Any) -> Dict[str, Any]:
    """Map a raw model finding to the manifest's per-issue schema."""
    if isinstance(item, dict):
        return {
            "severity": coerce_str(item.get("severity"), default="info"),
            "line": _coerce_line(item.get("line")),
            "message": coerce_str(item.get("message")),
            "suggestion": coerce_str(item.get("suggestion")),
        }
    # Non-object finding (e.g. a bare string): keep the content, zero the rest.
    return {
        "severity": "info",
        "line": 0,
        "message": coerce_str(item),
        "suggestion": "",
    }


async def handle(input_data: dict, provider) -> dict:
    """Review a workspace file and return structured findings + a summary."""
    file_path = require(input_data, "file_path", str, "path to the file to review")
    focus = coerce_str(input_data.get("focus"), default="all") or "all"
    if focus not in _FOCUS_VALUES:
        raise SkillInputError(
            f"focus must be one of {sorted(_FOCUS_VALUES)}, got {focus!r}"
        )

    content = _read_workspace_file(file_path)

    prompt = (
        f"File: {file_path}\n"
        f"Review focus: {focus}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Review the file above ONLY for the '{focus}' focus "
        "(report genuine issues found in the shown code, with their real "
        "line numbers). If nothing is found, use an empty issues array.\n\n"
        'Return a single JSON object with keys "issues" (array of objects '
        'with "severity" [string], "line" [integer], "message" [string], '
        '"suggestion" [string]) and "summary" (string), describing ONLY the '
        "file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    # Normalise to the manifest's output_schema so the executor's output
    # validation always sees well-typed values, regardless of how chatty or
    # sparse the model's raw reply was. Content itself (what the issues say,
    # which lines they point to, the summary text) always comes from the
    # model's reply about the real file — only the TYPES are normalised here.
    issues: List[Dict[str, Any]] = [
        _normalise_issue(item) for item in as_list(data.get("issues"))
    ]
    return {
        "issues": issues,
        "summary": coerce_str(data.get("summary")),
    }
