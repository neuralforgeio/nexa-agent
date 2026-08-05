# Nexa Agent Master Tools Plan — Batch A
> v4.7.0 — 14 frontend UX tools + 8 backend hardening tools
> Approved: 2026-08-05 by user
> Status: AUTONOMOUS EXECUTION (hybrid per tool)

## Protocol Enforcement
**PLAN FIRST** → REVIEW → IMPLEMENT → TEST → QA → VERSION SYNC → PUSH

---

## Batch A Breakdown

### A1: Stop generation + message actions (F-01, F-02) → v4.7.0-rc1
- F-01: abort streaming via button + AbortController
- F-02: copy/regenerate/edit/branch toolbar + inline edit
- files: Composer.tsx, MessageBubble.tsx
- tests: unit + integration

### A2: Session UX (F-03..F-05) → v4.7.0-rc2
- F-03: sidebar search with FTS5 + nav highlight
- F-04: cut group by Today/Yesterday/Archive in backend + pin/archive UI
- F-05: provider/model picker in header
- files: Sidebar.tsx, page.tsx, src/server.py (new /api/sessions?q=, /api/sessions/:id PATCH)
- tests: unit + API contract

### A3: Theme + shortcuts + mobile capture (F-06..F-10) → v4.7.0-rc3
- F-06: theme toggle with CSS vars + ThemeProvider
- F-07: keyboard shortcuts overlay
- F-08: connection status banner
- F-09: settings modal esc/trap/scroll-lock
- F-10: mobile responsive @ 390px
- files: SettingsPanel.tsx, page.tsx, lib/theme.ts (if needed), CommandPalette.tsx additions
- tests: each component tested with RTL + jest

### A4: Advanced UX + export +/orches (F-11..F-14) → v4.7.0
- F-11: file upload drag-drop + image paste
- F-12: export transcript/md/json
- F-13: command palette with fuzzy search
- F-14: onboarding wizard for first-run
- files: Composer.tsx (+ UploadButton), Sidebar (+helpers), CommandPalette.tsx, Onboarding.tsx
- new: /api/sessions/export/:id
- full integration tests with backend mock

### B1: Backend API Hardening (B-01..B-05) → v4.7.1
- B-01: 404s for missing IDs (sessions, memory, provider, export) with clear errors
- B-02: XSS markdown escape on export
- B-03: SSE hard timeout 60s on chat stream + emit error on abort
- B-04: preflight test before provider activation
- B-05: payload length limits (10KB max) on all POST endpoints
- files: src/server.py + tests/test_server_routes.py
- tests: endpoint contract + integration

### B2: Rate limiting + telemetry (B-06..B-08) → v4.7.1-rc
- B-06: slowapi rate limits
- B-07: usage aggregator (/api/usage)
- B-08: orchestrator stream events SSE
- files: src/server.py, nexa/state.py (+ cost aggregation)
- tests: verify 429 response format, SSE bridge works

---

## Quality Gate per Phase

- 1003+ tests pass (pre-existing; no regression)
- 14 new tests per F category (3-5 per feature)
- npm lint + build clean
- tsc --noEmit clean
- nexa --version + doctor pass

## Escalation Triggers
- Any P0/P1 bug found → stop → report → user
- Breaking change discovered during impl → stop → user
- 3 fix attempts failed → stop → report
- Security issue → stop → user

## Rollback Plan
- Each batch has its own `nexa-demo-frontend-v4.7*` branch
- If anything breaks: git revert the batch branch, push report, stop

## Estimated duration
- Phase A1-A4: 3–4 days (parallelize where possible)
- Phase B1-B2: 2–3 days

**Approved to proceed?** (I'm in Full Access Mode per your instruction)