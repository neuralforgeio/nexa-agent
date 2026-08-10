# Task: FIX-QA-P0-CLI-GRP2 — Repair the remaining 9 confirmed defects

Task ID: FIX-QA-P0-CLI-GRP2
Agent: OpenCode (kimi-k3) — SOP/Protocol v9 (Apex)
Timestamp: 2026-08-10
Mode: S5/S6 WRITE (authorized by user: "gas A, B, C berurutan")
Baseline: HEAD=9e8e147 (pushed). Full suite green: 1117 passed, 13 skipped, 0 failed.

## 1. Objective
Fix the remaining 9 CONFIRMED defects from QA-VERIFICATION-v503 (P0-5 partial, P0-6, P0-7,
P1-7, P1-8, P1-9, P1-10, P1-11, P1-12), each with a regression guard, no regressions.

## 2. Defects + planned fix (minimal, evidence-anchored)
| ID | Root (file:line) | Minimal fix |
|----|------------------|-------------|
| P0-5 | src/server.py:1029 ws_terminal(websocket), :1244 ws_approval(websocket) — missing `: WebSocket` annotation | Add `: WebSocket` annotation to both handlers (FastAPI treats unannotated param as query param -> 422/403). Guards confirmed still pass. |
| P0-6 | ui_tui/render/layout.py — `render_chat_area` imported but `layout["chat"]` never `.update()`d | Call `layout["chat"].update(render_chat_area(state))` in both sidebar-open and closed branches. |
| P0-7 | nexa/ shim package missing (mandate) | **USER DECISION PENDING -> see §9.** Default action this task: create minimal `nexa/__init__.py` compatibility shim re-exporting openforge.core symbols with a DeprecationWarning, per mandate. |
| P1-7 | ui_tui/panels/skills_panel.py — `ERROR` used (46,94) not imported | Add `ERROR` to the `from ui_tui.core.theme import ...` list IF theme defines it; else define local `ERROR = "bold red"` matching palette semantics. Must verify theme.py first. |
| P1-8 | openforge/provider.py:224 `_get_client()` outside try/except in chat_stream | Wrap client acquisition so missing credentials yield `("error", ...)` tuple instead of raising. Minimal edit: move into the existing try or add a guarded preamble. |
| P1-9 | ui_tui/render/panels.py:198 `state.persona.detail_open` (attr undefined) | Add `detail_open: bool = False` field to the persona badge/state class (verify its definition in ui_tui/core/state.py) OR guard with getattr(state.persona,"detail_open",False). Choose least-intrusive after reading state.py. |
| P1-10 | ui_tui/commands.py `_DISPATCH` (393-412) lacks `/exit`,`/quit` (advertised at 72-73) | Add `"/exit": cmd_exit, "/quit": cmd_exit` to _DISPATCH; define cmd_exit to signal quit (verify TUI quit mechanism first). |
| P1-11 | src/server.py:1616 `timeout=180.0` vs terminal_tool.MAX_TIMEOUT=60.0 | Use `timeout=min(180.0, MAX_TIMEOUT)` -> effectively 60, OR clamp to MAX_TIMEOUT explicitly. Minimal: pass allowed max. Verify sandbox-build intent. |
| P1-12 | src/server.py:1244 ws_approval lacks verify_token_ws | Add `verify_token_ws(websocket.query_params.get("token"))` at handler start, mirroring ws_terminal:1055. |

## 3. Scope (files to modify)
src/server.py, ui_tui/render/layout.py, ui_tui/panels/skills_panel.py, ui_tui/core/theme.py (verify ERROR),
openforge/provider.py, ui_tui/render/panels.py, ui_tui/core/state.py (verify persona field),
ui_tui/commands.py, nexa/__init__.py (new). Plus one regression test file. No dependency edits.

## 4. Non-Goals (verified unchanged at end)
- No version bump / no tag / no release (reserved for step C).
- No public API break; WS handlers gain annotation (bugfix, restores routing).
- No unrelated refactors / formatting. Do not alter test semantics of unrelated suites.

## 5. Baseline Snapshot
- HEAD 9e8e147; suite `1117 passed, 13 skipped, 0 failed`; git clean at start.

## 6. Impact Radius
- WS routing (P0-5,P1-12), TUI rendering (P0-6,P1-7,P1-9,P1-10), provider error path (P1-8),
  sandbox-build timeout clamp (P1-11), compat shim (P0-7).

## 7. Contract Stability
- All restore intended behavior; no breaking schema/API change. provider chat_stream error path changes
  from raise->yield('error',...) which matches documented contract (P1-8 is a conformance fix).

## 8. Test Strategy
- New regression file tests/test_grp2_fixes.py covering: layout chat update path, skills_panel ERROR
  import resolves, commands _DISPATCH has /exit+/quit, provider error yields tuple (offline), panels persona
  detail_open guard, server ws handlers annotated, sandbox timeout clamped, nexa shim importable.
- Re-run full suite; compare to 1117 baseline (+ new tests).

## 9. Decision Escalation (P0-7)
Mandate question surfaced to user separately. Plan default = build the shim (compat) since the mandate
exists and QA flagged its removal as a regression. Awaiting confirmation only if user prefers removal.

## 10. Abortion Criteria
- Full suite falls below 1117 passed after fixes -> revert that hunk.
- WS annotation change breaks FastAPI route registration (verify app still imports + routes 404/403 list).
- TUI fixes require a redesign rather than a 1-2 line update -> escalate, do not over-engineer.

## 11. Rollback Strategy
- `git checkout -- <files>` + delete new test/shim artifacts. <5 min, no data loss.

## 12. Release Strategy Preview
- After these fixes + suite green -> step C: PATCH v5.1.1 (Section 17 iron-law ceremony).

## 13. Knowledge Artifacts
- tests/test_grp2_fixes.py; update .plans/qa/QA-VERIFICATION-v503.md statuses; worklog append.
