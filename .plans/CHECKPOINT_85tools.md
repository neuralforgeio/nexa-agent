# Nexa Agent — 85-tools Roadmap Checkpoint (v4.8.0)
# Executable by a FRESH agent with zero prior context. (Protocol §11)
# Generated: 2026-08-07

## How to resume (read this in order — no guessing)
1. Read this file fully.
2. Verify ground truth before touching anything:
     git log --oneline -3 ; git status --short
     .venv/Scripts/python.exe -m pytest tests/test_backend_hardening.py -q
     npx vitest run   (from nexa_web/)   → expect ~80 passed
3. Read `.plans/current_task.md` (if present) next.
4. Only then start coding. One tool per commit. Never batch claims.

## Working directory / environment (Windows, pwsh)
- Repo root: C:\Users\Dearly Febriano\nexa-agent
- Python: use repo venv explicitly → `.venv/Scripts/python.exe`
  (NOTE: bare `uv` is NOT on PATH — always call the venv python: `.venv/Scripts/python.exe -m pip ...`)
- Frontend tests/build:
    cd nexa_web; npx vitest run
    npm run build            (repo root — wraps `cd nexa_web && next build`)
- Git: remote `origin` → https://github.com/neuralforgeio/nexa-agent (credentials already on machine; push to `main`, no branches)
- Version is mirrored in: pyproject.toml, nexa_web/package.json, package.json, config.yaml

## Current state (verified, evidence tags)
- Version [E]: v4.8.0 on main; tags v4.7.0, v4.8.0 pushed.
- HEAD [E]: c108395 chore(release) bump v4.8.0
- Tests [E]: pytest 1018 passed / 3 FAILED pre-existing (terminal timeout/truncation:
  tests/test_terminal_tool.py::TestConfigurableTimeout::test_timeout_actually_triggers,
  tests/test_terminal_tool.py::TestOutputTruncation::test_no_output_message,
  tests/test_tool_registry.py::test_terminal_command_timeout)
  → These 3 FAIL identically on clean baseline 8666192 (verified via git stash). NOT a regression. Do not "fix" by accident; it's out of scope unless asked.
- vitest [E]: 80 passed / 12 files. next build [E]: OK.

## Done — Category 1 (F-01..F-14, v4.7.0) & Category 2 (B-01..B-08, v4.8.0)
Category 1 frontend UX (all committed):
  F-01 stop (page.tsx + Composer, abortRef), F-02 message actions (MessageBubble,
  copy/regenerate/edit/branch; backend branch endpoint), F-03 search (Sidebar
  search box + GET /api/sessions?q= FTS, list_conversations(query,include_archived)),
  F-04 pin/archive (state.py _ensure_column pinned/archived + set_conversation_flags +
  PATCH title/pinned/archived + Sidebar UI grouping pinned/Today/Yesterday/Older/
  Archived), F-05 ModelPicker, F-06 ThemeProvider/Toggle, F-07 ShortcutsHelp,
  F-08 ConnectionStatusBanner, F-09 SettingsPanel Esc+focus-trap+scroll-lock,
  F-10 useMediaQuery + mobile drawer (lib/useMediaQuery.ts), F-11 upload
  (POST /api/upload → NEXA_WORKSPACE/uploads + Composer paperclip/drag-drop/paste),
  F-12 export per-session (GET /api/export/{id}?format=md|json + Sidebar Download),
  F-13 CommandPalette, F-14 Onboarding.
Category 2 backend hardening (all committed):
  B-01 404s (sessions get/delete, memory delete, export, provider/test),
  B-02 export HTML-escapes tool blocks (stored-XSS) + ?format=json,
  B-03 hard 60s asyncio.timeout on chat SSE + error event,
  B-04 pre-flight reg.test() before /api/provider/use (refuse 400 on fail),
  B-05 max 10240-char message → 400 on /api/chat/stream,
  B-06 slowapi Limiter (60/min) on /api/chat/stream (optional dep, no-op if absent),
  B-07 GET /api/usage (state.usage_stats: token aggregation per day/session),
  B-08 GET /api/orchestrator/stream (live SSE snapshot loop).
  New tests: tests/test_backend_hardening.py (11 pass), tests/test_sessions_search_upload.py (8 pass).

## Next to do — remaining roadmap (NOT done; verify code before assuming)
Category 3 (M-01..M-10) → bump to v4.9.0. Deps NOT yet installed:
  pypdf, python-docx, python-pptx, sqlite-vec, mcp  (install via .venv/Scripts/python.exe -m pip)
  Files to create: tools/mcp_client.py; nexa/vector_db.py; nexa/embeddings.py;
  agent/workspace_indexer.py; tools/core/{semantic_search,read_pdf,read_docx,read_xlsx,read_pptx}.py;
  modify tools/core/read_file.py (auto-detect by extension).
Category 4 (C-01..C-05) → v4.10.0. C-01/C-02 are STUBS (NotImplementedError).
  C-03 VLM via existing provider; C-04/C-05 Web Speech API in Composer/MessageBubble.
Category 5 (H-01..H-08) → v4.11.0. ApprovalModal, /ws/approval, DiffViewer,
  OpenTelemetry (opentelemetry-instrumentation-fastapi), Langfuse, nexa/cost_tracker.py,
  /api/usage already exists (extend), nexa/audit.py hash-chain.
Category 6 (S-01..S-10) → v4.12.0. autopilot/swarm/reflexion/watcher/harvester/
  tot_planner/scheduler/plugin_manifest + `nexa plugin install` CLI + PluginMarketplace UI.
Category 7 (D-01..D-10) → v4.13.0. Brew/APT/RPM/exe/msi are STUBS; Dockerfile real;
  VS Code/JetBrains/Neovim stubs; PWA (manifest.json + sw.js in nexa_web/public).
Category 8 (I-01..I-10) → v4.14.0. Persona/SelfImprovement persistence, ReasoningChain,
  ContextCompressor recursive, semantic_memory + memory_consolidator wiring, cost-aware
  + capability-aware failover, prompt caching.
Category 9 (SEC-01..SEC-10) → v4.15.0 FINAL. Fuzzing suites (path traversal/XSS/SQLi/
  cmd-injection/unicode), oversized input, rate-limit fuzz, auth bypass, CSRF/origin,
  pip-audit + npm audit (0 critical).

## Locked decision ledger (do not re-litigate without new evidence)
- F-01..F-14 & B-01..B-08 marked DONE based on running tests + build, not memory.
- 3 terminal-timeout test failures are PRE-EXISTING (proven vs baseline). Leave them.
- slowapi + python-multipart added as pinned deps (pyproject). Reproducibility: keep
  lockfiles; do NOT delete uv.lock / nexa_web/package-lock.json.
- B-03 uses asyncio.timeout(60) around the whole stream; keepalive pings remain 15s.
- B-04 intentionally refuses blind activation (400) when provider test fails.

## Open risks / honesty notes
- /api/orchestrator/stream polls (0.5s) rather than event-push; acceptable snapshot-SSE
  for now, but a true push (orchestrator event bus) is the correct long-term design.
- Rate limiter is per-process (slowapi in-memory) — not suitable behind multi-worker
  uvicorn without a shared store. Flagged for Kategori 9/ops follow-up.
- /api/upload sanitizes filename & caps at 10 MiB, but there is no MIME sniffing.
- Promotion candidate: consider fixing the 3 pre-existing terminal-timeout tests in a
  dedicated, separately-scoped change (NOT during feature pushes).

## Quick-resume commands
  git log --oneline -2
  .venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/integration
  cd nexa_web && npx vitest run && npm run build
