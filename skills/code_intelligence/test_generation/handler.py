"""
Skill: test_generation
======================

Generate unit tests (``pytest`` or ``unittest``) for a source file inside the
workspace, optionally targeting one function. Returns the generated test
code, the suggested test file path, and the model's estimated line coverage
percentage.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``FORGE_WORKSPACE``.
  * ``filesystem:workspace:write`` — declared by the manifest; this handler
    does NOT itself write the generated tests to disk (see the honesty note).

Honesty note: the test code and the coverage estimate come from the model's
reply to a prompt that embeds the *actual* file contents read from disk —
nothing here is stubbed or pre-canned. The returned ``test_file_path`` is a
suggested path string only (``tests/test_<stem>.py`` or a user-mirroring
equivalent); the file is NOT written by this handler, so nothing claims a
test suite exists that has never been executed. ``coverage_estimate`` is the
model's own estimate of the tests it just generated, coerced and clamped to
0-100 — it is a static prediction, not a measured coverage run.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Dict, Optional

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

_FRAMEWORKS = ("pytest", "unittest")

SYSTEM = (
    "You are Forge's test-generation engine. You are given the REAL contents "
    "of a source file and a target framework (pytest or unittest). Write "
    "genuine, runnable unit tests against ONLY the code actually shown — "
    "never invent functions, classes, or behaviour that are not present. "
    "Respond with a SINGLE JSON object, and nothing else (no markdown "
    "fences, no prose around it), with exactly these keys:\n"
    '  "test_code": a string containing the complete test file source, '
    "using the requested framework, with correct imports.\n"
    '  "test_file_path": a string with a sensible repo-relative path for the '
    "test file (e.g. tests/test_<module>.py).\n"
    '  "coverage_estimate": an integer 0-100 estimating the percentage of '
    "the source file's lines your generated tests would exercise."
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
            f"(resolved to {p})"
        )
    return p.read_text(encoding="utf-8", errors="replace")


def _derive_test_path(file_path: str) -> str:
    """Derive ``tests/test_<stem>.py`` (mirroring subdirectories when any)."""
    rel = PurePosixPath(file_path.replace("\\", "/"))
    stem = rel.stem or "module"
    parents = [part for part in rel.parts[:-1] if part not in ("", ".")]
    return str(PurePosixPath("tests", *parents, f"test_{stem}.py"))


async def handle(input_data: dict, provider) -> dict:
    """Generate tests for a workspace source file with the given framework."""
    file_path = require(input_data, "file_path", str, "path to the source file")
    framework = require(input_data, "framework", str, "pytest | unittest")
    if framework not in _FRAMEWORKS:
        raise SkillInputError(
            f"framework must be one of {list(_FRAMEWORKS)}, got {framework!r}"
        )

    function_name: Optional[str] = input_data.get("function_name")
    if function_name is not None and not isinstance(function_name, str):
        raise SkillInputError(
            f"field 'function_name' must be str, got {type(function_name).__name__}"
        )

    content = _read_workspace_file(file_path)
    suggested_path = _derive_test_path(file_path)

    focus = (
        f"Focus the tests on the function/method named '{function_name}' "
        "(plus whatever helpers it directly exercises)."
        if function_name
        else "Cover the file's public functions/classes."
    )
    prompt = (
        f"File: {file_path}\n"
        f"Framework: {framework}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        f"Generate a complete {framework} test file for the code above. "
        f"{focus}\n"
        f"Suggested test file location: {suggested_path}\n\n"
        'Return a single JSON object with keys "test_code" (string, the '
        'full test file source), "test_file_path" (string), and '
        '"coverage_estimate" (integer 0-100), describing ONLY the file '
        "content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    test_code = coerce_str(data.get("test_code"), default="")
    if not test_code.strip():
        # Refuse to fabricate tests from nothing — fail loudly rather than
        # satisfy the output contract with an empty payload.
        raise SkillOutputError(
            "test_generation: model reply contained no usable 'test_code'"
        )

    test_file_path = coerce_str(data.get("test_file_path"), default="").strip()
    if not test_file_path:
        test_file_path = suggested_path

    raw_estimate = data.get("coverage_estimate")
    estimate = int(round(coerce_number(raw_estimate, default=0.0)))
    coverage_estimate = max(0, min(100, estimate))

    return {
        "test_code": test_code,
        "test_file_path": test_file_path,
        "coverage_estimate": coverage_estimate,
    }
