"""
Skill: documentation_generation
===============================

Generate documentation for a workspace file. The ``doc_type`` input chooses
the format: ``docstring`` (module/function docstrings for the file),
``readme`` (a README section explaining the file), ``api_reference``
(a structured reference of the public surface), or ``all`` (all three
combined). The handler returns the rendered documentation text plus the list
of files that were created or updated on disk.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``.
  * ``filesystem:workspace:write`` — declared by the manifest to *allow*
    auto-writing, but this handler deliberately does NOT write: see the
    honesty note below.

Honesty note: the ``documentation`` string comes from the model's reply to a
prompt that embeds the *actual* file contents read from disk — nothing here
is stubbed, template-generated, or pre-canned. If the model's reply is not
parseable JSON, ``ValueError`` propagates rather than fabricating docs.
This handler does NOT modify any files: ``updated_files`` is always the
(empty) honest list of files it actually wrote. Callers that want the docs
persisted must write ``documentation`` themselves (e.g. via
:func:`agent.tool_api.write_workspace_file`).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_number, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]

_DOC_TYPE_VALUES = ("docstring", "readme", "api_reference", "all")

_DOC_INSTRUCTIONS = {
    "docstring": (
        "Write comprehensive docstrings (module-level plus every function, "
        "class, and method actually present in the file), following the "
        "codebase style implied by the shown code. Present the documented "
        "code/docstrings as the documentation."
    ),
    "readme": (
        "Write a README section documenting what this file does, its key "
        "entry points, and a short usage example grounded in the real code "
        "shown. Use markdown."
    ),
    "api_reference": (
        "Write a structured API reference for the public surface actually "
        "present in the file: for each public function/class/method show the "
        "signature, parameters, return value, and a one-line description. "
        "Use markdown headings and lists."
    ),
    "all": (
        "Write ALL of: (1) comprehensive docstrings for the module and every "
        "function/class/method actually present, (2) a README section with "
        "a usage example, and (3) a structured API reference for the public "
        "surface. Combine them into one markdown document with headings."
    ),
}

SYSTEM = (
    "You are Nexa's documentation engine. You are given the REAL contents of "
    "a single source file plus a documentation type (docstring | readme | "
    "api_reference | all). Write documentation that describes ONLY what is "
    "actually in the shown code — real module/function/class names, real "
    "signatures, real behaviour. Never invent APIs, parameters, or examples "
    "that reference identifiers not present in the file. Respond with a "
    "SINGLE JSON object, and nothing else (no markdown fences around the "
    "JSON, no prose around it), with exactly this key:\n"
    '  "documentation": a string containing the rendered documentation '
    "(markdown/docstring text as appropriate for the requested type)."
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
    """Generate documentation for a workspace file (no auto-writing)."""
    file_path = require(input_data, "file_path", str, "path to the file to document")
    doc_type = require(input_data, "doc_type", str, "documentation type")
    if doc_type not in _DOC_TYPE_VALUES:
        raise SkillInputError(
            f"doc_type must be one of {sorted(_DOC_TYPE_VALUES)}, got {doc_type!r}"
        )

    content = _read_workspace_file(file_path)
    instruction = _DOC_INSTRUCTIONS[doc_type]

    prompt = (
        f"File: {file_path}\n"
        f"Documentation type: {doc_type}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Task: {instruction}\n\n"
        'Return a single JSON object with key "documentation" (string) '
        "containing documentation for ONLY the file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    documentation = coerce_str(data.get("documentation"))
    if isinstance(data.get("documentation"), (list, dict)):
        # Some models nest docs; flatten them honestly into text form.
        import json

        documentation = json.dumps(data["documentation"], indent=2)

    # Honest contract: this handler does not write anything to disk, so the
    # list of updated files is empty by definition. The caller may persist
    # `documentation` itself if desired.
    return {
        "documentation": documentation,
        "updated_files": [],
    }
