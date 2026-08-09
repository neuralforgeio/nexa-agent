# OpenForge — TODO Master (v4.0.0 + Web UI Redesign)

> **Current version**: v4.0.0 (Enterprise Workspace overhaul)
> **Status**: v4.0.0 in progress. v3.0.0 released.

## 🚀 v4.0.0 — Enterprise Workspace (In Progress)

### Fixed in v4.0.0
- [x] **C1.1** LLM timeout → 600s default via `FORGE_LLM_TIMEOUT` env (`forge/provider.py`)
  - Root cause: llamacpp canceled task id after 22s — client was using default OpenAI SDK timeout
  - Fix: `AsyncOpenAI(timeout=float(os.environ.get("FORGE_LLM_TIMEOUT", "600")))`
- [x] **C1.2** Duplicate-request guard: `inFlightRef` in `forge_web/app/page.tsx`
  - Previously possible to trigger 2 parallel processing loops; now blocked
- [x] **C2.1** Sandbox right panel (50/50 Preview+Terminal) — `components/SandboxPanel.tsx`
  - Auto-detects `localhost:3000/5173/4321/4200/8080` dev servers → iframe preview
  - Draggable divider; split position persisted to `localStorage` (`forge-sandbox-split`)
  - Modes: split / preview-only / terminal-only
- [x] **C2.2** Collapsible sidebar via `Ctrl+B`, sandbox via `Ctrl+J`
  - State persisted across restarts; mobile-friendly drawer removed in favor of toggles
- [x] **C2.3** `WorkingProcess` dropdown component (`components/WorkingProcess.tsx`)
  - Streams thinking steps, tool calls, memory events live
  - Auto-collapses 800ms after completion; shows one-line summary
- [x] **C2.4** TerminalPanel embed mode: `embedded` prop removes fixed positioning
- [x] **C2.5** TypeScript pinned to 5.9.3 (was 7.0.2 native — build worker crash)
- [ ] **C2.6** Session management — delete confirmation + rename (sidebar currently deletes immediately)

### In Progress
- [ ] **C3** Local `.openforge` install script (read-only builtins + writable `~/.openforge/tools/custom/`)
- [ ] **C4** E-commerce demo build monitored in sandbox
- [ ] **C5** MIT headers propagated to all source files

---

## ✅ v3.0.0 Completed (Pragmatic Scope)

### P0 — Critical Bug Fixes
- [x] P0.1 Memory wiring (`build_system_prompt` with `memory_digest` + `user_profile`)
- [x] P0.2 `ErrorMemory.save()` in conversation_loop
- [x] P0.3 Failover chain wiring + real provider swap on `advance()`
- [x] P0.4 Terminal security: block `~/.openforge/` access (`is_protected_path_reference`)
- [x] P0.5 FORGE_SECRETS_DIR + ProviderRegistry

### P1 — Provider Expansion
- [x] P1.1 tokenrouter + databricks in catalog (8 providers total)
- [x] P1.2 ProviderRegistry module (load `~/.openforge/secrets/providers.json`)
- [x] P1.3 `forge provider add/use/list/remove/test` interactive CLI
- [x] P1.4 `/provider` slash command extended (CLI + TUI dispatcher)
- [x] P1.5 HTTP `/api/provider` endpoints + SettingsPanel.tsx frontend

### P2 — Documentation
- [x] P2.1 SYSTEMPROMPT.md complex (10 sections, creator attribution)
- [x] P2.2 LICENSE MIT extended (9 clauses: attribution, trademark, patent, etc.)
- [x] P2.3 Tool call card persistence (frontend)
- [x] P2.4 docs/providers.md update (TokenRouter + Databricks + custom endpoint)

### P3 — UI Polish
- [x] P3.1 TerminalPanel.tsx + WebSocket `/ws/terminal`

### P4 — Services & E2E
- [x] server.py running (port 8000), 30 routes, health 200
- [x] Frontend dev server running (port 3000), HTTP 200
- [x] Provider API tested (add tokenrouter mock → masked key, switched active)
- [x] Terminal security tested (`cat ~/.openforge/.env` → blocked)
- [x] SSE stream tested (session → thinking → error → end)

### P5 — Roadmap
- [x] .plans/ROADMAP_20_FEATURES.md written (20 features, 5 phases)

### P6 — Release
- [x] pyproject.toml 2.1.0 → 3.0.0
- [x] forge_web/package.json 2.1.0 → 3.0.0
- [x] worklog.md Task 22
- [x] .plans/STATE.json update
- [x] CONTINUATION_PROMPT.md update
- [x] Git commit + push + tag v3.0.0 + GitHub Release

---

## ⏳ Deferred to v3.1+ (See ROADMAP_20_FEATURES.md)

The 20-feature enterprise blueprint is written in `.plans/ROADMAP_20_FEATURES.md`.
Execution is deferred because the pragmatic scope (bug fixes + providers + docs
+ UI polish) is more urgent and delivers immediate value.

| Phase | Features | Target |
|-------|----------|--------|
| v3.1.0 | Semantic Vector Memory, File Patch Rollback, Ask Question Mode, Trajectory Export | Medium |
| v3.2.0 | Auto User Profile, Web Scraping, Thinking Panel, Self-Healing Deps | Medium |
| v3.3.0 | Cross-Session Context, Git Automation, Tool Viz, Smart Routing | High |
| v3.4.0 | Predictive Tool Chaining, BG Process Mgr, xterm.js Full, Observability | High |
| v3.5.0 | Knowledge Graph, AST Sandbox, Artifact Panel, MCP Client | Very High |

---

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
