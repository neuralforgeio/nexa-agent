# OpenForge — 20 Planning & Intelligence Tools (v4.0.0)

> **Goal.** Give Forge the deepest tool-belt of any local agent: true planning,
> filesystem intelligence, git-native reasoning, and self-extending tooling —
> all confined to the FORGE_WORKSPACE sandbox (read-only tools may read project
> files but never mutate outside the workspace).

Design principles (applied to all 20):

1. **Tools never raise.** Every function returns ``ToolResult(ok=True/False)``.
2. **Workspace-scoped writes.** Tools that mutate filesystem state use
   ``resolve_in_workspace``; read-only tools accept absolute paths for
   analysis but never modify anything.
3. **Composable.** Tools chain naturally: ``task_plan`` → ``todo_write`` →
   ``project_scaffold`` → ``git_checkpoint``.
4. **Serializable outputs.** Everything returns a Markdown string (LLM-friendly).
5. **Full OpenAI schemas.** Each tool exposes a ``*_SCHEMA`` dict —
   registered in ``tools/registry.py`` and tested in ``tests/test_planning_tools.py``.

---

## A. Planning & Reasoning (the "thinking" tier)

| # | Tool | What it does |
|---|------|--------------|
| 1 | ``task_plan`` | Decompose a high-level goal into an ordered, dependency-aware DAG of subtasks with per-task effort/risk. Deterministic templates for common patterns (`build a web app`, `fix a bug`, `write tests`, `research X`) + generic decomposition for everything else. |
| 2 | ``todo_write`` | Create/update a named TODO file in the workspace (``.openforge/todos/<name>.md``). Check/uncheck items, add/remove items. The task-management backbone every long-running agent needs. |
| 3 | ``todo_read`` | Read a TODO file (or list them all). `todo_read` + `todo_write` together are a persistent scratch-pad the LLM can consult across turns. |
| 4 | ``scratchpad_write`` | Free-form notes to ``.openforge/scratchpad.md`` (append or replace). The agent's working memory between tool calls. |
| 5 | ``think`` | A loop-back reasoning tool: pass a `thought` and optional `next_action`; returns the thought plus a nudge. Lets models reason *explicitly* without polluting the final answer (pairs with the Working Process panel). |

## B. Filesystem Intelligence

| # | Tool | What it does |
|---|------|--------------|
| 6 | ``list_directory`` | Recursive-or-shallow directory tree with sizes, type filter, and glob exclude (`node_modules`, `.git`, etc.). Complements `read_file` for exploration. |
| 7 | ``search_files`` | Recursive regex search through text files with file glob, context lines, byte cap 256 KB, and workspace-scoped safety. (Like `grep -R` but sandboxed.) |
| 8 | ``file_info`` | Stat: size, mtime, MIME guess, line count, sha256. |
| 9 | ``project_scaffold`` | Generate starter scaffolds: ``next`` (Next.js pages/layout/tsconfig), ``vite-react``, ``express`` API, ``fastapi``, ``python-cli``, ``static`` (HTML/CSS/JS). Writes `package.json`/`requirements.txt` + entry files + `.gitignore`. |

## C. Git-Native Reasoning (workspace-local)

| # | Tool | What it does |
|---|------|--------------|
| 10 | ``git_diff`` | Show working-tree or staged diff in unified format (size-capped). |
| 11 | ``git_status`` | Porcelain status + branch + last commit. |
| 12 | ``git_log`` | N recent commits with shortened hash and subject. |
| 13 | ``git_checkpoint`` | Stage-and-commit a named snapshot inside the workspace (only if the workspace is a git repo). Lets the agent roll back work it just did. |

## D. Process & Systems

| # | Tool | What it does |
|---|------|--------------|
| 14 | ``list_ports`` | Detect common dev-server ports (3000, 3001, 5173, 8000, 8080, 4173) and whether each is listening — the "is my preview server up" tool. |
| 15 | ``process_snapshot`` | Lightweight process snapshot for the *current* user (name, pid, cmdline) via `tasklist`/`ps`, filtered by a regex. Helps the agent kill stale servers. |

## E. Knowledge & State

| # | Tool | What it does |
|---|------|--------------|
| 16 | ``memory_search`` | FTS5 search over long-term memories + messages (via `ConversationDB.search_*`). Returns rank-ordered snippets with source pointers. |
| 17 | ``session_search`` | FTS5 search over past conversations — lets Forge recall any previous session by keyword. |
| 18 | ``web_fetch`` | Fetch a URL (10s timeout, 32 KB cap, simple HTML→text) and return the readable text. Complements `web_search` with actual page content. |

## F. Self-Extension (the "getting smarter" tier)

| # | Tool | What it does |
|---|------|--------------|
| 19 | ``create_tool`` | Draft a new Forge tool: writes ``~/.openforge/tools/<name>.py`` (the *user-writable* tool folder) with docstring, `*_SCHEMA`, and an async entry. Forge can then call it — the agent literally extends itself (MIT-licensed, attribution still belongs to Dearly Febriano Irwansyah per LICENSE §2). |
| 20 | ``plan_and_delegate`` | Meta-tool: call ``task_plan`` and, for each top-level task, provide a suggested sub-delegate prompt for the existing ``delegate`` tool — the recursive-planner hook. |

---

### Implementation layout

```
tools/
└── planning/
    ├── __init__.py            # register_planning_tools(registry) helper
    ├── todos.py               # task_plan, todo_write, todo_read
    ├── scratchpad.py          # scratchpad_write, think
    ├── fs_intelligence.py     # list_directory, search_files, file_info, project_scaffold
    ├── git_tools.py           # git_diff, git_status, git_log, git_checkpoint
    ├── process_tools.py       # list_ports, process_snapshot
    ├── knowledge_tools.py     # memory_search, session_search, web_fetch
    └── self_extend.py         # create_tool, plan_and_delegate
```

The user-writable tools directory `~/.openforge/tools/` is scanned at registry
build time (``load_user_tools()``) so anything ``create_tool`` drafts is
immediately usable in the *next* conversation turn.
