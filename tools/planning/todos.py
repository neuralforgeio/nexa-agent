"""
OpenForge — Planning Tools: Task Plan + TODO Lists (v4.1.0)
=============================================================

Three tools:

- :func:`task_plan`  — decompose a goal into a dependency-aware subtask DAG.
- :func:`todo_write` — create/update a TODO list in the workspace.
- :func:`todo_read`  — read a TODO list (or list them all).

TODO lists live in ``<workspace>/.openforge/todos/<name>.md`` using the GitHub
task-list syntax::

    - [ ] pending item
    - [x] done item

``task_plan`` uses a set of deterministic templates for the most common
user goals (web app, bug fix, test suite, research, refactor) and falls back
to a generic 5-phase plan otherwise. The output is always Markdown so it
can be pasted into ``todo_write`` directly.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from tools._paths import resolve_in_workspace as _resolve_in_workspace


def resolve_in_workspace(raw: str):
    """Module-level wrapper so tests can monkeypatch path resolution."""
    return _resolve_in_workspace(raw)


# ---------------------------------------------------------------------------
# task_plan
# ---------------------------------------------------------------------------
_TEMPLATES: Dict[str, List[str]] = {
    "web-app": [
        "Clarify scope & success criteria",
        "Design data model / API surface",
        "Scaffold project with project_scaffold",
        "Implement core pages/components",
        "Wire state management & data fetching",
        "Add error handling & loading states",
        "Style + accessibility pass",
        "Write tests (unit + e2e smoke)",
        "Manual QA with sandbox preview",
        "Deploy/build + docs",
    ],
    "bug-fix": [
        "Reproduce the bug",
        "Write a failing regression test",
        "Locate the root cause (search_files + file_info)",
        "Apply minimal fix",
        "Verify test passes",
        "Scan for similar bugs elsewhere (search_files)",
        "Update docs if behaviour changed",
    ],
    "refactor": [
        "Read current implementation",
        "Identify code smells / hot paths",
        "Plan the new structure",
        "Refactor in small safe steps",
        "Run tests after every step",
        "Clean up dead code",
    ],
    "research": [
        "Frame the question precisely (query_reformulator)",
        "Search the web for primary sources (web_search)",
        "Fetch + extract facts (web_fetch)",
        "Cross-validate ≥2 sources",
        "Synthesize a summary with citations (deep_research)",
        "Store learnings in memory",
    ],
    "tests": [
        "Inventory existing coverage",
        "Identify untested public functions",
        "Write unit tests (happy path + edge cases)",
        "Write integration tests",
        "Run the full suite, fix flaky tests",
        "Document the testing strategy",
    ],
}


def _classify_goal(goal: str) -> str:
    """Return the template key best matching the goal text."""
    g = goal.lower()
    if any(k in g for k in ("bug", "fix", "error", "broken", "regression", "crash")):
        return "bug-fix"
    if any(k in g for k in ("refactor", "rename", "clean up", "restructure")):
        return "refactor"
    if any(k in g for k in ("research", "learn", "investigate", "explain how")):
        return "research"
    if any(k in g for k in ("web", "react", "next", "vue", "angular", "frontend", "landing", "dashboard", "ecommerce", "e-commerce", "app ui", "website")):
        return "web-app"
    if any(k in g for k in ("test", "coverage", "pytest", "jest", "spec")):
        return "tests"
    return "generic"


def _generic_steps(goal: str) -> List[str]:
    """Produce a generic 5-phase plan for goals with no template match."""
    return [
        f"Clarify exactly what '{goal[:50]}' should achieve",
        "Explore the workspace to understand current state (list_directory, search_files)",
        "Design the approach (write to scratchpad)",
        "Implement step by step",
        "Verify the result works",
        "Document what was done",
    ]


async def task_plan(goal: str, project_path: str = "", max_steps: int = 12) -> str:
    """
    Decompose a high-level goal into an ordered, dependency-aware plan.

    Returns Markdown containing:
      - a concise summary line,
      - the template used (or ``generic``),
      - the ordered subtasks (GitHub task-list format, ready for
        :func:`todo_write`).

    Args:
        goal:         The user's high-level goal in natural language.
        project_path: Optional workspace sub-path for context (unused for now,
                      reserved for future path-aware scoring).
        max_steps:    Maximum number of subtasks to emit (default 12).

    Returns:
        A Markdown plan document.
    """
    goal = goal.strip()
    if not goal:
        return "**Error.** `goal` cannot be empty."

    key = _classify_goal(goal)
    steps = list(_TEMPLATES.get(key) or _generic_steps(goal))
    steps = steps[: max(3, max_steps)]

    lines = [
        f"# Plan — {goal}",
        "",
        f"*Template: `{key}`* · *{len(steps)} steps*",
        "",
        "## Subtasks",
        "",
    ]
    for i, step in enumerate(steps, 1):
        # Mark dependencies implicitly via numbered order.
        lines.append(f"{i}. [ ] {step}")
    lines += [
        "",
        "## Next action",
        "",
        "Start with step 1. Check items off with ``todo_write`` as you go.",
    ]
    return "\n".join(lines)


TASK_PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "The user's high-level goal."},
        "project_path": {"type": "string", "description": "Optional workspace sub-path for context.", "default": ""},
        "max_steps": {"type": "integer", "description": "Max subtasks (default 12).", "default": 12},
    },
    "required": ["goal"],
}


# ---------------------------------------------------------------------------
# TODO storage helpers
# ---------------------------------------------------------------------------
_TODO_DIR_REL = ".openforge/todos"


def _todo_dir():
    """Return the absolute todo directory inside the workspace (creating it)."""
    ws = resolve_in_workspace(".")
    d = ws / _TODO_DIR_REL
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_name(name: str) -> str:
    """Make a TODO list name filesystem-safe (letters, digits, -, _)."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower()
    return name or "default"


def _todo_path(name: str):
    """Return the absolute path for a named TODO list."""
    return _todo_dir() / f"{_sanitize_name(name)}.md"


# ---------------------------------------------------------------------------
# todo_write
# ---------------------------------------------------------------------------
async def todo_write(
    items: List[str],
    name: str = "default",
    mode: str = "replace",
    checked: Optional[List[str]] = None,
) -> str:
    """
    Create or update a TODO list in the workspace.

    ``mode="replace"`` overwrites the list with ``items``.
    ``mode="append"`` adds the items to the end.
    ``checked`` lists item texts to mark as done (``[x]``).

    The file lives at ``.openforge/todos/<name>.md`` so users can inspect/edit
    it directly in their editor.

    Args:
        items:   List of task descriptions ("Write tests", …).
        name:    The TODO list name (default "default").
        mode:    ``replace`` or ``append``.
        checked: Optional list of item texts to mark as completed.

    Returns:
        A short confirmation with the resulting list content.
    """
    if not isinstance(items, list):
        return "**Error.** `items` must be a list of strings."

    path = _todo_path(name)
    existing = ""
    if mode == "append" and path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")

    normalized = [it.strip() for it in items if str(it).strip()]
    checked_set = set(checked or [])

    lines: List[str] = [f"# TODO — {name}", ""]
    for it in normalized:
        mark = "[x]" if it in checked_set else "[ ]"
        lines.append(f"- {mark} {it}")

    body = (existing.rstrip() + "\n" if existing else "") + "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    return (
        f"Todo list `{name}` saved — {len(normalized)} item(s), "
        f"{len(checked_set)} marked done. Path: `.openforge/todos/{_sanitize_name(name)}.md`"
    )


TODO_WRITE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {"type": "string"}, "description": "Task descriptions."},
        "name": {"type": "string", "description": "TODO list name.", "default": "default"},
        "mode": {"type": "string", "enum": ["replace", "append"], "default": "replace"},
        "checked": {"type": "array", "items": {"type": "string"}, "description": "Item texts to mark done."},
    },
    "required": ["items"],
}


# ---------------------------------------------------------------------------
# todo_read
# ---------------------------------------------------------------------------
async def todo_read(name: str = "") -> str:
    """
    Read a TODO list, or list all TODO lists when ``name`` is empty.

    Args:
        name: The list name (default: list all lists).

    Returns:
        The list contents as Markdown, or an index of all lists.
    """
    if name:
        path = _todo_path(name)
        if not path.exists():
            return f"Todo list `{name}` not found."
        content = path.read_text(encoding="utf-8", errors="replace")
        remaining = sum(1 for l in content.splitlines() if l.startswith("- [ ]"))
        done = sum(1 for l in content.splitlines() if l.startswith("- [x]"))
        return f"{content}\n\n---\n*{done} done, {remaining} remaining.*"

    # List all.
    d = _todo_dir()
    files = sorted(d.glob("*.md"))
    if not files:
        return "No TODO lists yet. Create one with `todo_write`."
    parts = ["# TODO lists", ""]
    for f in files:
        content = f.read_text(encoding="utf-8", errors="replace")
        remaining = sum(1 for l in content.splitlines() if l.startswith("- [ ]"))
        done = sum(1 for l in content.splitlines() if l.startswith("- [x]"))
        parts.append(f"- **{f.stem}** — {done} done · {remaining} remaining")
    return "\n".join(parts)


TODO_READ_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "List name (empty = all).", "default": ""},
    },
    "required": [],
}
