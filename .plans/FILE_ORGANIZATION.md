# Nexa Agent — File & Folder Organization Plan (v4.0.0)

> **Why.** The project grew organically across 4 major versions. Newcomers
> open the repo and see 40+ top-level entries, three different "agent"
> packages (``agent/``, ``nexa/agent/``, ``agentskills/`` mentioned in
> docs) and can't tell what's canonical. This document defines the
> **target tree** and the **safe migration order**, so a human maintainer
> can finish the re-org in small, reviewable PRs instead of one giant
> breaking change.

Rules we follow:

1. **Public surface stays stable.** ``nexa/``, ``agent/``, ``tools/`` keep
   their import paths — existing code (`from nexa.provider import …`)
   must not break. Re-exports via ``__init__.py`` do the heavy lifting.
2. **Each directory has one job.** A file belongs to the directory whose
   README paragraph names it.
3. **Folder inside folder** is allowed where the nested grouping is the
   natural mental model (see ``tools/planning/`` as the working example).
4. **Nothing is deleted without its tests moving with it.**

---

## 1. Target tree (goal state)

```
nexa-agent/
│
├── README.md                  ← product overview, quickstart, screenshots
├── LICENSE                    ← MIT (copyright Dearly Febriano Irwansyah)
├── pyproject.toml             ← single source of truth for version
├── uv.lock / bun.lock         ← dependency locks
│
├── docs/                      ← long-form docs (architecture, guides)
│   ├── architecture.md
│   ├── tools/
│   │   ├── planning-tools.md  ← the 20 v4.0 tools (auto-generated list)
│   │   └── user-tools.md      ← how to write ~/.nexa/tools/*.py
│   ├── deployment/
│   │   ├── windows.md
│   │   └── linux.md
│   └── images/                ← logo, screenshots
│
├── nexa/                      ← core Python package (stable public API)
│   ├── __init__.py
│   ├── bootstrap.py           ← stdio UTF-8 + NEXA_HOME warmup
│   ├── config.py              ← constants + env loading
│   ├── state.py               ← ConversationDB (SQLite + FTS5)
│   ├── process_manager.py     ← singleton locks (v4.0)
│   ├── provider.py            ← LLMProvider (OpenAI-compat streaming)
│   ├── provider_registry.py   ← runtime provider store
│   ├── provider_failover.py   ← failover chain
│   └── agent/                 ← thin shims re-exporting from agent/
│       └── client_session.py
│
├── agent/                     ← 33 intelligence modules (public API)
│   ├── __init__.py            ← re-exports for the modules below
│   ├── conversation_loop.py   ← the main iterative tool-calling loop
│   ├── prompt_builder.py      ← system-prompt assembler
│   ├── reasoning_chain.py     ← ReAct-style step tracking
│   ├── <28 other modules>
│   └── planning/              ← (FUTURE) folding planning into agent/ too
│       ├── task_planner.py    ← wraps tools.planning.todos.task_plan
│       └── todo_tracker.py
│
├── tools/                     ← tool-belt (33 tools as of v4.0)
│   ├── __init__.py
│   ├── registry.py            ← ToolRegistry + create_default_registry
│   ├── _paths.py              ← shared workspace-boundary helper
│   ├── _schemas.py            ← Pydantic arg validation
│   │
│   ├── file_tools.py          ← read_file, write_file
│   ├── file_patch_tool.py     ← file_patch, revert_file
│   ├── terminal_tool.py       ← run_terminal_command, bg processes
│   ├── terminal_exec_tool.py  ← terminal_exec (session-aware)
│   ├── code_execution_tool.py ← code_execution (HITL sandboxed)
│   ├── web_search_tool.py     ← web_search (DDG)
│   ├── delegate_tool.py       ← delegate
│   │
│   └── planning/              ← v4.0 planning toolkit (package)
│       ├── __init__.py        ← register_planning_tools()
│       ├── todos.py           ← task_plan, todo_write, todo_read
│       ├── scratchpad.py      ← scratchpad_write, think
│       ├── fs_intelligence.py ← list_directory, search_files, file_info, project_scaffold
│       ├── git_tools.py       ← git_status, git_diff, git_log, git_checkpoint
│       ├── process_tools.py   ← list_ports, process_snapshot
│       ├── knowledge_tools.py ← memory_search, session_search, web_fetch
│       └── self_extend.py     ← create_tool, plan_and_delegate
│
├── providers/                 ← provider catalog + resolution
│   ├── __init__.py
│   └── catalog.py             ← PROVIDER_CATALOG + resolve_provider()
│
├── nexa_cli/                  ← `nexa` CLI (entry point, subcommands)
│   ├── __init__.py
│   └── main.py
│
├── ui_tui/                    ← `nexa-tui` rich TUI client
│   ├── __init__.py
│   └── app.py
│
├── tui_gateway/               ← (reserved) gateway sidecar for TUI/web
│   ├── __init__.py
│   └── server.py
│
├── nexa_web/                  ← Next.js web UI (LOCAL only, not on PyPI)
│   ├── package.json
│   ├── next.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           ← chat page (sidebar + main + sandbox)
│   │   └── globals.css
│   ├── components/
│   │   ├── Sidebar.tsx        ← session history (Ctrl+B)
│   │   ├── Composer.tsx       ← input + attach button
│   │   ├── MessageBubble.tsx  ← user/stacked assistant bubble
│   │   ├── WorkingProcess.tsx ← nested thinking trace, auto-collapse
│   │   ├── ThinkingIndicator.tsx ← legacy thinking dots (kept for tests)
│   │   ├── TerminalPanel.tsx  ← xterm.js PTY terminal
│   │   ├── SandboxPanel.tsx   ← right sidebar: Preview top / Terminal bottom
│   │   └── SettingsPanel.tsx  ← provider management UI
│   ├── lib/
│   │   ├── stream.ts          ← SSE client with reconnect backoff
│   │   └── theme.ts           ← design tokens + types
│   └── public/
│       └── nexa-agent.png     ← logo
│
├── scripts/                   ← install & helper scripts (cross-platform)
│   ├── install.ps1            ← Windows installer
│   ├── install.sh             ← Linux/macOS installer
│   ├── orion.py               ← llama.cpp helper
│   ├── configure_orion.py
│   └── check_docstrings.py
│
├── tests/                     ← pytest suite (603 passing as of v4.0.0)
│   ├── test_tool_registry.py
│   ├── test_planning_tools.py ← 36 tests covering the 20 new tools
│   ├── test_memory_system.py
│   ├── test_terminal_tool.py
│   └── …                      ← (one file per subsystem, flat)
│
├── nexa-workspace/            ← the FS sandbox tools are confined to
│   └── .gitkeep
│
├── .plans/                    ← internal planning/state — NOT shipped
│   ├── STATE.json             ← active milestone checkpoint
│   ├── TODO_MASTER.md         ← current backlog
│   ├── ROADMAP_20_FEATURES.md
│   ├── PLANNING_TOOLS_20.md   ← the v4.0 tool design doc
│   └── FILE_ORGANIZATION.md   ← this file
│
├── worklog.md                 ← session log (chronological, append-only)
├── CONTINUATION_PROMPT.md     ← bootstrap text for future chats
└── .env.example               ← env-vars reference
```

---

## 2. Migration order (low-risk, testable each step)

Work one step per PR; run the full test suite between steps.

1. **Move ``docs/README_PLUGIN_ICON.html`` → ``docs/images/``** (pure move, no refs).
2. **Move ``tools/planning/`` imports** under ``nexa.tools.planning`` via
   ``tools/planning/__init__.py`` aliases so public paths keep working.
3. **Fold ``nexa_cli/`` into ``nexa/cli/``** with a forwarding shim in
   ``nexa_cli/__init__.py`` (``from nexa.cli import main``). Tests already
   cover entry points, they must stay green.
4. **Fold ``tui_gateway/`` + ``ui_tui/`` into ``nexa/ui/`` sub-packages.**
5. **Consolidate ``agent/`` + ``nexa/agent/``**: the only module in
   ``nexa/agent/`` is ``client_session.py``. Move it to
   ``agent/client_session.py`` and leave ``nexa/agent/__init__.py`` with
   a deprecation shim.
6. **Consolidate test helpers** into ``tests/_helpers/`` (faker builders,
   common fixtures). No test file gets longer than ~300 lines — split by
   subsystem, not concern.
7. **Group ``nexa_web/components/`` into subfolders**:
   ``components/chat/``, ``components/sandbox/``, ``components/settings/``.

Each step keeps ``.venv/Scripts/python.exe -m pytest tests/ -q`` green.

---

## 3. "Folder inside folder" guidance

Nesting is a win when the grouping mirrors how a maintainer thinks.

Good nestings in the current codebase:

- ``tools/planning/`` — the 20 planning tools are one mental unit.
- ``nexa_web/components/sandbox/`` *(target)* — SandboxPanel + TerminalPanel.
- ``docs/deployment/`` — per-platform install docs.

Avoid:

- Nested ``utils/`` inside another package (split by domain instead).
- ``tests/nexa/agent/…`` — tests stay flat; they map to *behaviors*,
  not packages.

---

## 4. What we did NOT do (yet)

- We did not rename the top-level Python package (``agent/``) — too many
  deep references inside the agent modules themselves.
- We did not flatten ``agent/`` — the 33 modules genuinely benefit from
  being one searchable directory.

These are explicit trade-offs for v4.x. Revisit at v5.0.
