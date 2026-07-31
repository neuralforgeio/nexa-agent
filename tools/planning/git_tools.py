"""
Nexa Agent — Planning Tools: Git-Native Reasoning (v4.0.0)
==========================================================

Wraps ``git`` inside the workspace so the agent can inspect diffs, track
progress, and create rollback checkpoints.

- :func:`git_status`    — branch + porcelain status + last commit.
- :func:`git_diff`      — unified diff of working tree or staged area.
- :func:`git_log`       — recent commits (short hash + subject + age).
- :func:`git_checkpoint`— stage-and-commit a snapshot so work can be rolled
  back with ``git revert`` later.

All commands run with ``cwd=NEXA_WORKSPACE`` (safe by construction), a
hardcoded timeout, and size-capped stdout so large diffs never blow up
context.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from tools._paths import resolve_in_workspace as _resolve_in_workspace


def resolve_in_workspace(raw: str):
    """Module-level wrapper so tests can monkeypatch path resolution."""
    return _resolve_in_workspace(raw)


_MAX_OUTPUT = 64 * 1024  # 64 KB cap on any single git command's output.


async def _run_git(args: List[str], cwd) -> tuple[int, str, str]:
    """Run a git command and return (rc, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "git command timed out"
    return proc.returncode or 0, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


def _truncate(text: str, limit: int = _MAX_OUTPUT) -> str:
    """Truncate text to the byte cap with an elision notice."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n\n…[truncated {len(text) - limit} chars]…\n\n" + text[-half:]


async def _workspace_is_repo(cwd) -> bool:
    """Return True if ``cwd`` is inside a git work tree."""
    rc, out, err = await _run_git(["rev-parse", "--is-inside-work-tree"], cwd)
    if rc == 0 and out.strip() == "true":
        return True
    # Windows git sometimes returns rc 128 with "not a git repository" but
    # on some builds emits rc 0 with empty stdout on a non-repo; also treat
    # missing git binary as "not a repo".
    if "not a git repository" in (err or "").lower():
        return False
    return rc == 0


async def git_status(path: str = ".") -> str:
    """
    Show the current branch and working-tree status (``git status --short``).

    Args:
        path: Workspace path (should be a git repo); default ".".

    Returns:
        A Markdown status report.
    """
    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not await _workspace_is_repo(root):
        return f"`{path or '.'}` is not a git repository (`git init` to start one)."

    rc_branch, branch, _ = await _run_git(["branch", "--show-current"], root)
    rc_last, last, _ = await _run_git(["log", "-1", "--pretty=format:%h · %s · %ar"], root)
    rc_status, status, _ = await _run_git(["status", "--short"], root)

    lines = [
        "# Git status",
        "",
        f"- **Branch:** `{branch.strip() or '(detached)'}`",
    ]
    if rc_last == 0 and last.strip():
        lines.append(f"- **Last commit:** {last.strip()}")
    lines += ["", "## Changes", ""]
    status = _truncate(status)
    if status.strip():
        lines.append("```")
        lines.append(status.rstrip())
        lines.append("```")
    else:
        lines.append("Working tree is clean. ✅")
    return "\n".join(lines)


GIT_STATUS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"path": {"type": "string", "default": "."}},
    "required": [],
}


async def git_diff(path: str = ".", staged: bool = False, file: Optional[str] = None) -> str:
    """
    Show a unified diff of the working tree (or ``--cached`` for staged).

    Args:
        path:   Workspace path (a git repo).
        staged: If True, diff the index against HEAD.
        file:   Optional path to a single file (relative to ``path``).

    Returns:
        A unified diff (Markdown code block).
    """
    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not await _workspace_is_repo(root):
        return f"`{path or '.'}` is not a git repository."

    args = ["diff"]
    if staged:
        args.append("--cached")
    if file:
        args += ["--", file]

    rc, out, err = await _run_git(args, root)
    if rc != 0:
        return f"**git diff failed:** {err.strip()}"
    if not out.strip():
        scope = "staged" if staged else "unstaged"
        return f"No {scope} changes in `{path or '.'}`."
    return f"```diff\n{_truncate(out)}\n```"


GIT_DIFF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "default": "."},
        "staged": {"type": "boolean", "default": False},
        "file": {"type": "string", "description": "Restrict to one file (optional)"},
    },
    "required": [],
}


async def git_log(path: str = ".", limit: int = 10) -> str:
    """
    Show recent commits.

    Args:
        path:  Workspace path (a git repo).
        limit: Number of commits to show (1–50).

    Returns:
        A Markdown bulleted list.
    """
    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not await _workspace_is_repo(root):
        return f"`{path or '.'}` is not a git repository."
    limit = max(1, min(limit, 50))
    rc, out, err = await _run_git(
        ["log", f"-n{limit}", "--pretty=format:%h · %s · %ar (%an)"], root
    )
    if rc != 0:
        return f"**git log failed:** {err.strip()}"
    if not out.strip():
        return "No commits yet."
    items = [f"- {line}" for line in out.strip().split("\n")]
    return "# Recent commits\n\n" + "\n".join(items)


GIT_LOG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "default": "."},
        "limit": {"type": "integer", "default": 10},
    },
    "required": [],
}


async def git_checkpoint(path: str = ".", message: str = "checkpoint") -> str:
    """
    Stage all changes and create a checkpoint commit in the workspace repo.

    After a checkpoint, previous state can be recovered via ``git revert``
    or ``git reset``. A no-op when the working tree is clean.

    Args:
        path:    Workspace path (a git repo).
        message: The commit message (default: "checkpoint").

    Returns:
        Confirmation with the new commit hash (or a no-op note).
    """
    try:
        root = resolve_in_workspace(path)
    except ValueError as exc:
        return f"**Error.** {exc}"
    if not await _workspace_is_repo(root):
        return f"`{path or '.'}` is not a git repository."

    rc_status, status, _ = await _run_git(["status", "--short"], root)
    if rc_status != 0:
        return "**Error.** Could not check git status."
    if not status.strip():
        return "Working tree already clean — nothing to checkpoint."

    rc_add, _, err_add = await _run_git(["add", "-A"], root)
    if rc_add != 0:
        return f"**git add failed:** {err_add.strip()}"

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"{message} (checkpoint {ts})"
    rc_com, out_com, err_com = await _run_git(["commit", "-m", full_msg], root)
    if rc_com != 0:
        return f"**git commit failed:** {err_com.strip()}"

    rc_hash, new_hash, _ = await _run_git(["rev-parse", "HEAD"], root)
    return (
        f"Checkpoint created: `{new_hash.strip()}` — *{full_msg}*\n\n"
        "Roll back with `git revert HEAD` or `git reset --hard HEAD~1` "
        "(run via `git_diff`'s workspace repo)."
    )


GIT_CHECKPOINT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "default": "."},
        "message": {"type": "string", "default": "checkpoint"},
    },
    "required": [],
}
