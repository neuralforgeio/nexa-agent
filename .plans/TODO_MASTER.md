# Nexa Agent — TODO Master (v3.0.0 + Roadmap)

> **Current version**: v3.0.0 (Ultimate Enterprise Evolution)
> **Status**: All P0-P3 phases complete. v3.0.0 release-ready.

## ✅ v3.0.0 Completed (Pragmatic Scope)

### P0 — Critical Bug Fixes
- [x] P0.1 Memory wiring (`build_system_prompt` with `memory_digest` + `user_profile`)
- [x] P0.2 `ErrorMemory.save()` in conversation_loop
- [x] P0.3 Failover chain wiring + real provider swap on `advance()`
- [x] P0.4 Terminal security: block `~/.nexa/` access (`is_protected_path_reference`)
- [x] P0.5 NEXA_SECRETS_DIR + ProviderRegistry

### P1 — Provider Expansion
- [x] P1.1 tokenrouter + databricks in catalog (8 providers total)
- [x] P1.2 ProviderRegistry module (load `~/.nexa/secrets/providers.json`)
- [x] P1.3 `nexa provider add/use/list/remove/test` interactive CLI
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
- [x] Terminal security tested (`cat ~/.nexa/.env` → blocked)
- [x] SSE stream tested (session → thinking → error → end)

### P5 — Roadmap
- [x] .plans/ROADMAP_20_FEATURES.md written (20 features, 5 phases)

### P6 — Release
- [x] pyproject.toml 2.1.0 → 3.0.0
- [x] nexa_web/package.json 2.1.0 → 3.0.0
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
