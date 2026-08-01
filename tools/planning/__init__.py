"""
Nexa Agent — Planning Toolkit (v4.1.0)
======================================

This package contains twenty production-grade planning, filesystem, git,
process, knowledge, and self-extension tools. Use
:func:`register_planning_tools` from :mod:`tools.registry` to attach them
all to a :class:`tools.registry.ToolRegistry` in one call.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from tools.planning.fs_intelligence import (
    FILE_INFO_SCHEMA,
    LIST_DIRECTORY_SCHEMA,
    PROJECT_SCAFFOLD_SCHEMA,
    SEARCH_FILES_SCHEMA,
    file_info,
    list_directory,
    project_scaffold,
    search_files,
)
from tools.planning.git_tools import (
    GIT_CHECKPOINT_SCHEMA,
    GIT_DIFF_SCHEMA,
    GIT_LOG_SCHEMA,
    GIT_STATUS_SCHEMA,
    git_checkpoint,
    git_diff,
    git_log,
    git_status,
)
from tools.planning.knowledge_tools import (
    MEMORY_SEARCH_SCHEMA,
    SESSION_SEARCH_SCHEMA,
    WEB_FETCH_SCHEMA,
    memory_search,
    session_search,
    web_fetch,
)
from tools.planning.process_tools import (
    LIST_PORTS_SCHEMA,
    PROCESS_SNAPSHOT_SCHEMA,
    list_ports,
    process_snapshot,
)
from tools.planning.scratchpad import (
    SCRATCHPAD_WRITE_SCHEMA,
    THINK_SCHEMA,
    scratchpad_write,
    think,
)
from tools.planning.self_extend import (
    CREATE_TOOL_SCHEMA,
    PLAN_AND_DELEGATE_SCHEMA,
    create_tool,
    plan_and_delegate,
)
from tools.planning.todos import (
    TASK_PLAN_SCHEMA,
    TODO_READ_SCHEMA,
    TODO_WRITE_SCHEMA,
    task_plan,
    todo_read,
    todo_write,
)

#: ``(name, fn, description, schema)`` tuples consumed by ``register_planning_tools``.
PLANNING_TOOLS = [
    # Planning & reasoning
    ("task_plan",        task_plan,        "Decompose a high-level goal into an ordered, dependency-aware subtask plan (Markdown, ready for todo_write).", TASK_PLAN_SCHEMA),
    ("todo_write",       todo_write,       "Create or update a named TODO list in the workspace.", TODO_WRITE_SCHEMA),
    ("todo_read",        todo_read,        "Read a TODO list, or list all TODO lists when name is empty.", TODO_READ_SCHEMA),
    ("scratchpad_write", scratchpad_write, "Write to the workspace scratchpad (working memory between tool calls).", SCRATCHPAD_WRITE_SCHEMA),
    ("think",            think,            "Loop-back reasoning tool — narrate an internal step explicitly. Pairs with the Working Process panel.", THINK_SCHEMA),
    # Filesystem intelligence
    ("list_directory",   list_directory,   "Tree-style listing of a workspace directory with sizes and glob excludes.", LIST_DIRECTORY_SCHEMA),
    ("search_files",     search_files,     "Recursive regex search over workspace text files.", SEARCH_FILES_SCHEMA),
    ("file_info",        file_info,        "Size, mtime, line count, MIME guess, sha256 for a workspace file.", FILE_INFO_SCHEMA),
    ("project_scaffold", project_scaffold, "Generate starter code for next / vite-react / express / fastapi / static / python-cli projects.", PROJECT_SCAFFOLD_SCHEMA),
    # Git
    ("git_status",       git_status,       "Show branch + working-tree status of a workspace repo.", GIT_STATUS_SCHEMA),
    ("git_diff",         git_diff,         "Unified diff of working tree or staged changes.", GIT_DIFF_SCHEMA),
    ("git_log",          git_log,          "Recent commits (short hash + subject + age).", GIT_LOG_SCHEMA),
    ("git_checkpoint",   git_checkpoint,   "Stage-and-commit a snapshot for later rollback.", GIT_CHECKPOINT_SCHEMA),
    # Process & systems
    ("list_ports",       list_ports,       "Report which common dev-server ports are listening on this machine.", LIST_PORTS_SCHEMA),
    ("process_snapshot", process_snapshot, "Regex-filtered snapshot of user processes.", PROCESS_SNAPSHOT_SCHEMA),
    # Knowledge
    ("memory_search",    memory_search,    "FTS5 search over Nexa's long-term memory store.", MEMORY_SEARCH_SCHEMA),
    ("session_search",   session_search,   "FTS5 search over past conversation messages.", SESSION_SEARCH_SCHEMA),
    ("web_fetch",        web_fetch,        "Fetch a URL and extract its readable text (32 KB cap).", WEB_FETCH_SCHEMA),
    # Self-extension
    ("create_tool",      create_tool,      "Write a brand-new Nexa tool into ~/.nexa/tools/ (usable next turn).", CREATE_TOOL_SCHEMA),
    ("plan_and_delegate", plan_and_delegate, "Plan a goal AND emit a ready delegate-prompt per step.", PLAN_AND_DELEGATE_SCHEMA),
]

__all__ = [t[0] for t in PLANNING_TOOLS] + ["PLANNING_TOOLS"]
