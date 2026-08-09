"""
OpenForge — summarization skill (web_research)
===============================================

Purpose
-------
Summarize inline ``content`` or a workspace file (``file_path``) at a chosen
``length`` (brief | standard | detailed) and ``style`` (bullet | paragraph |
executive). Returns the manifest contract: ``summary`` (str), ``key_points``
(list of str) and ``word_count`` (int).

Permissions
-----------
Declared: ``filesystem:workspace``, ``memory:read``. When ``file_path`` is
given the handler resolves it inside the sandboxed Forge workspace via
``agent.tool_api.workspace_path``; paths escaping the workspace or missing
files are rejected with :class:`skills.registry.SkillInputError`.

Honesty note
------------
The ``summary`` and ``key_points`` are produced entirely by the provider
model from the REAL source text (inline content or the file actually read
from disk) — the source is embedded verbatim in the prompt. ``word_count``
is computed in code as the true whitespace-token count of the returned
summary, never copied from the model. If the model omits required keys they
fall back to schema-valid empties (never invented prose); LLM errors and
unparseable JSON propagate to the caller.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict

from skills._common import ask_llm_json, as_list, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle", "SYSTEM"]

_LENGTHS = ("brief", "standard", "detailed")
_STYLES = ("bullet", "paragraph", "executive")

SYSTEM = (
    "You are a precise summarization engine inside the OpenForge skills "
    "system. Summarize the user's source text honouring the requested length "
    "(brief, standard, or detailed) and style (bullet, paragraph, or "
    "executive). Never invent facts that are not in the source. Respond with "
    "a single JSON object and nothing else — no prose, no markdown fence. "
    "The object MUST have these keys:\n"
    '  "summary": string — the summary in the requested style;\n'
    '  "key_points": array of strings — the most important points.'
)


def _load_source(input_data: Dict[str, Any]) -> str:
    """Return the real source text from inline content or a workspace file."""
    content = input_data.get("content")
    file_path = input_data.get("file_path")
    if content is not None and not isinstance(content, str):
        raise SkillInputError(
            f"field 'content' must be str, got {type(content).__name__}"
        )
    if file_path is not None and not isinstance(file_path, str):
        raise SkillInputError(
            f"field 'file_path' must be str, got {type(file_path).__name__}"
        )
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(file_path, str) and file_path.strip():
        from agent import tool_api  # late import: keeps skill import light

        try:
            resolved = tool_api.workspace_path(file_path)
        except ValueError as exc:
            raise SkillInputError(f"invalid file_path: {exc}") from exc
        if not resolved.is_file():
            raise SkillInputError(f"workspace file not found: {file_path!r}")
        return resolved.read_text(encoding="utf-8", errors="replace")
    raise SkillInputError("provide non-empty 'content' or a valid 'file_path'")


def _build_prompt(source: str, length: str, style: str) -> str:
    """Embed the real source text plus the requested length/style."""
    return (
        f"Requested length: {length}\n"
        f"Requested style: {style}\n"
        "Source text to summarize (verbatim):\n"
        f"{source}"
    )


async def handle(input_data: dict, provider) -> dict:
    """
    Summarize the input and return ``summary``/``key_points``/``word_count``.

    Raises:
        SkillInputError: No usable source, bad types, bad enums, or a
            ``file_path`` that is invalid or missing in the workspace.
        RuntimeError:    The provider signalled an LLM error (never swallowed).
        ValueError:      The model reply contained no parseable JSON object.
    """
    source = _load_source(input_data)

    length = coerce_str(input_data.get("length"), default="standard").strip().lower()
    if length not in _LENGTHS:
        length = "standard"
    style = coerce_str(input_data.get("style"), default="paragraph").strip().lower()
    if style not in _STYLES:
        style = "paragraph"

    data = await ask_llm_json(provider, _build_prompt(source, length, style), system=SYSTEM)

    summary = coerce_str(data.get("summary"), default="")
    key_points = [coerce_str(p) for p in as_list(data.get("key_points"))]
    key_points = [p for p in key_points if p]

    result: Dict[str, Any] = {
        "summary": summary,
        "key_points": key_points,
        # Computed honestly in code: the real word count of the summary.
        "word_count": len(summary.split()),
    }
    return result
