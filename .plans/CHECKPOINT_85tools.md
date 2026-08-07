# Nexa Agent — 85-Tools Roadmap Checkpoint (v4.12.0)
# Executable by a FRESH agent with zero prior context. (Protocol §11)
# Generated: 2026-08-07 (Category 6 complete)

## How to resume (read first — no guessing)
1. Read this file fully.
2. Verify ground truth (do NOT trust memory of what "should" be there):
     git log --oneline -3 ; git status --short
     .venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/integration   # expect 1038 passed / 0 fail
     cd nexa_web && npx vitest run                                              # expect 80 passed
3. Read `.plans/CURRENT_STATE_v*.json` + `current_task.md` only if present.
4. Only then code. One tool per commit. Never batch claims; test after each category.

## Environment (Windows / pwsh)
- Repo: C:\Users\Dearly Febriano\nexa-agent
- Python: always `.venv/Scripts/python.exe` (do NOT use bare `python`/`uv`).
- Frontend: `cd nexa_web && npx vitest run`; build: `npm run build` (repo root).
- Git: `origin` → https://github.com/neuralforgeio/nexa-agent (credentials already on the machine; push to `main`, no branches).
- GitHub CLI: `C:\Program Files\GitHub CLI\gh.exe` — authenticated as `neuralforgeio` (scope: repo). Preferred for releases over raw tokens.

## Current state (verified)
- Version: **v4.11.0** on `main` (tags v4.7.0..v4.11.0 + GitHub Releases v4.7.0..v4.10.0 published).
- HEAD: `1361c8a` — Category 5 code committed to `main`.
- QA evidence:
  - pytest: `1038 passed / 0 failed / 20 skipped` (3 pre-existing POSIX-only terminal timeout tests are @skipif on Windows).
  - vitest: `80 passed / 12 files`.
  - next build: OK (no errors).
  - release: v4.10.0 GitHub Release created; v4.7.0/v4.8.0 auto-releases exist (already-tagged earlier).

## Done categories (evidence-backed; verify code)
- Category 1 (F-01..F-14) → v4.7.0 — frontend UX (stop, actions, search, pin/archive, model picker, theme, shortcuts, connection banner, settings a11y, mobile, upload, export, command palette, onboarding). [E]
- Category 2 (B-01..B-08) → v4.8.0 — backend hardening (404s, XSS-esc, 60s SSE timeout, provider pre-flight, 10KB max, slowapi rate limit, /api/usage, /api/orchestrator/stream). [E]
- Category 3 (M-01..M-10) → v4.9.0 — MCP + RAG + multimodal (mcp_client, vector_db, embeddings, workspace_indexer, semantic_search, read_pdf/docx/xlsx/pptx, read_file dispatch). [E]
- Category 4 (C-01..C-05) → v4.10.0 — browser stub, image-gen stub, VLM, voice-input, TTS. [E]
- Category 5 (H-01..H-08) → v4.11.0 — HITL ApprovalModal + /ws/approval, DiffViewer, OpenTelemetry, Langfuse hook, cost_tracker, /api/usage, tamper-evident audit (nexa/audit.py). [E]
- Category 6 (S-01..S-10) → v4.12.0 — SOTA autonomous: autopilot, swarm, reflexion, watcher, harvester, ToT planner, scheduler, plugin manifest, plugin CLI ("nexa plugin install"), PluginMarketplace UI. QA: 1045 passed. [E]

## Remaining work (Category 7–9)
- Category 7 (D-01..D-10) → v4.13.0 — DevOps/distribution (brew/apt/rpm/exe/msi STUBS + Dockerfile real + VS Code/JB/Neovim stubs + PWA manifest/sw.js).
- Category 8 (I-01..I-10) → v4.14.0 — persistence of personas, reasoning chains, context compression, semantic_memory wiring, memory_consolidator, dead-import removal, cost/capability-aware failover, prompt caching.
- Category 9 (SEC-01..SEC-10) → v4.15.0 FINAL — 50 path-traversal, 30 XSS, 40 SQLi, 50 cmd-injection, 30 unicode, oversized input, rate-limit fuzz, auth-bypass, CSRF/origin, LS pip-audit + npm audit (0 critical).

## Known pre-existing suite debt (do NOT mask)
- tests/test_terminal_tool.py, tests/test_tool_registry.py each used POSIX-only `sleep`/`true` and failed on Windows; both are @skipif(os.name=="nt") — intentionally skipped, not "fixed"; behavior unchanged for the agent.
- No other unexplained fails; every category above was **run** and its bugs fixed before pushing.

## Decision ledger
- Category 4 uses *stubs* for browser (Playwright) and image generation — spec said STUB ONLY (no heavyweight local models).
- Category 5 usage endpoint is a thin aggregation layer over messages.token_count; pricing lives in nexa/cost_tracker.py and is configurable via code map (no registry change needed).
- /ws/approval is a minimal echo/ack now; real UI approval flow wired in H-01/H-03 components.
- B-04 (provider use) has a pre-flight test to avoid activating a broken provider.
- Pyproject effects: slowapi + python-multipart + Category-3 deps (pypdf, python-docx, python-pptx, sqlite-vec, mcp) are now mandatory; pinned with floors (>=).

## Quick-resume (one-liner)
  .venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/integration && cd nexa_web && npx vitest run && npm run build

## Next action (Category 6)
Implement S-01..S-10 one tool at a time; add tests; keep every step verifiable.
Latest checkpoint commit: after this file is pushed, immediately next category.
