"""
Skill: performance_profiling
============================

Analyse a source file inside the workspace under a described runtime
scenario and report likely performance bottlenecks. Each bottleneck has a
type, a code location, an impact assessment, and an optimisation
suggestion; the skill also returns an overall profile summary.

Permissions used:
  * ``filesystem:workspace`` — the file referenced by ``file_path`` is read
    through :func:`agent.tool_api.workspace_path`, i.e. sandboxed to
    ``NEXA_WORKSPACE``.
  * ``terminal:execute`` — declared by the manifest; this handler does NOT
    execute the target code (see the honesty note).

Honesty note: this is STATIC ANALYSIS. No profiler is run, no code is
executed, and no timings are measured — the bottlenecks and summary come
from the model's reply to a prompt that embeds the *actual* file contents
read from disk plus the user's scenario description. Every claim in the
output is therefore an informed prediction about the real code, not a
measurement, and the prompt instructs the model to say exactly that rather
than fabricate benchmark numbers.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent import tool_api
from skills._common import as_list, ask_llm_json, coerce_str, require
from skills.registry import SkillInputError

__all__ = ["handle"]

SYSTEM = (
    "You are Nexa's performance-profiling engine operating in STATIC "
    "ANALYSIS mode: you are given the REAL contents of a source file and a "
    "runtime scenario, but you have NOT executed the code and have NO "
    "profiler timings. Identify likely bottlenecks strictly from the code "
    "actually shown — never invent functions, lines, or measurements, and "
    "never present fabricated benchmark numbers as fact. Respond with a "
    "SINGLE JSON object, and nothing else (no markdown fences, no prose "
    "around it), with exactly these keys:\n"
    '  "bottlenecks": an array of objects, each with EXACTLY the string '
    'keys "type" (e.g. "algorithmic", "io", "memory", "concurrency"), '
    '"location" (function/class/line area in the file), "impact" (how much '
    'it matters under the scenario), and "suggestion" (a concrete '
    "optimisation). Use an empty array if the code has no plausible "
    "bottlenecks.\n"
    '  "profile_summary": a string summarising the static-analysis findings '
    "for the scenario, explicitly noting that no live profiling was run."
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


def _normalise_bottleneck(item: Any) -> Dict[str, str]:
    """Coerce one raw bottleneck entry into the manifest's object shape."""
    if isinstance(item, dict):
        return {
            "type": coerce_str(item.get("type"), default="unknown") or "unknown",
            "location": coerce_str(item.get("location"), default="") ,
            "impact": coerce_str(item.get("impact"), default=""),
            "suggestion": coerce_str(item.get("suggestion"), default=""),
        }
    # A bare string from the model still carries information — keep it
    # honestly as the suggestion rather than dropping it.
    text = coerce_str(item, default="")
    return {"type": "unknown", "location": "", "impact": "", "suggestion": text}


async def handle(input_data: dict, provider) -> dict:
    """Statically profile a workspace file under the described scenario."""
    file_path = require(input_data, "file_path", str, "path to the source file")
    scenario = require(input_data, "scenario", str, "runtime scenario description")
    if not scenario.strip():
        raise SkillInputError("field 'scenario' must not be empty")

    content = _read_workspace_file(file_path)

    prompt = (
        f"File: {file_path}\n"
        f"Scenario: {scenario}\n\n"
        f"FILE CONTENT (verbatim, read from the workspace):\n"
        f"-----\n{content}\n-----\n\n"
        "Perform a static-analysis performance review of this code under the "
        "scenario above. Do NOT claim to have run a profiler or measured "
        "timings; reason from the code only.\n\n"
        'Return a single JSON object with keys "bottlenecks" (array of '
        'objects with string keys "type", "location", "impact", '
        '"suggestion") and "profile_summary" (string), describing ONLY the '
        "file content shown above."
    )

    data: Dict[str, Any] = await ask_llm_json(provider, prompt, system=SYSTEM)

    bottlenecks: List[Dict[str, str]] = [
        _normalise_bottleneck(item) for item in as_list(data.get("bottlenecks"))
    ]

    return {
        "bottlenecks": bottlenecks,
        "profile_summary": coerce_str(data.get("profile_summary"), default=""),
    }
