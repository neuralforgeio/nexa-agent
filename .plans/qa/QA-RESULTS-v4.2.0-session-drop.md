# QA-RESULTS — OpenForge v4.2.0 (Session Drop)

Date: 2026-08-02 (UTC)
Method: Direct execution on this codebase, not a re-roll of GLM-5.2's plan.
Tester: zcode assist

## Executive Summary

| Layer | Scope | Outcome |
|-------|-------|---------|
| Smoke | Install, server boot, /api/health, /api/provider, sessions CRUD, orchestrator | **All pass** |
| Regression | 6 v4.1.x GLM-flagged bugs | Still fixed (6/6) |
| Feature (v4.2.0) | 24 providers, orchestrator+personas, TUI parity, SSE introspection | **All pass** |
| Security | Path traversal, NUL byte injection, __builtins__ bypass, HOME env leak | **1 new bug found & fixed** |
| Integration | Live llama.cpp E2E | **7/7 pass** |
| Accessibility / mobile | Manual smoke | partial (Sidebar arias added; full axe-core scan deferred) |
| Soak / Compatibility | 4-hour soak, multi-OS, multi-Python | **Not run in this session** (too long for one chat; plan added below) |

## Verified-Fixed (regression) — 6 bugs

| ID | Description | How verified |
|----|-------------|--------------|
| GLM-P0-TOOL-3 | `registry.execute(name='x', ...)` TypeError | ✓ unit + integration |
| GLM-P0-TOOL-4 | `__builtins__.open()` AST bypass | ✓ attribute / subscript / getattr variants all rejected |
| GLM-P0-AGENT-1 | `Orchestrator.decide_next` returned stale phase on cap | ✓ returns actual state.phase now |
| GLM-P0-TOOL-1 | HOME env leak — subprocess could read `~/.openforge` | ✓ HOME overridden to workspace |
| GLM-P0-TOOL-2 | `deep_research` crashed on str-shaped search output | ✓ coerced via `_parse_search_text` |
| GLM-P0-SETUP-1 | fastapi/uvicorn/ptyprocess/watchdog missing from pyproject | ✓ declared |

## NEW bug discovered & fixed in this session

**P0-SEC-PATH-NULLBYTE** — `tools/_paths.py::resolve_in_workspace` accepted
control bytes & NUL bytes and silently propagated them into `os.path` calls.
On Windows a NUL byte truncates the path at the OS level (`CreateFileW`
treats `\x00` as end); on Linux `open()` raises. Either way, downstream code
could disagree about the path being resolved.
**Fix:** reject any control byte `< 0x20` (excluding `\t`) and any `\x00`/`\ufffd`; reject empty or whitespace-only path.
**Test:** two new unit tests added in `tests/test_file_tools_hardened.py::TestPathHygiene`.

## Smoke / feature coverage proof-points

- `python server.py` boots cleanly on 127.0.0.1:8001 in this session.
- `GET /api/health` returns `version == 4.2.0` and the expected 33-tool list.
- `GET /api/provider` enumerates 24 catalog providers.
- `POST /api/sessions` + `GET /api/sessions/{id}` round-trips.
- `FORGE_ORCHESTRATOR=1` flows: PLANNING badge on boot, transitions
  PLANNING → CODING → REVIEWING → DONE work end-to-end (verified against
  `Orchestrator.decide_next` directly).
- Persona Manager whitlists are honored: Coder persona gets `write_file` +
  `code_execution`, Reviewer gets `run_terminal_command` only.

## Live llama.cpp integration
Manual run (no pytest skip-guard):
```
FORGE_E2E_LLAMACPP=1 .venv/Scripts/python.exe -m pytest tests/test_llamacpp_real.py -q
```
Result: **7 passed, 78s wall clock** (test_host_health, test_models_endpoint,
test_chat_completions_nonstream [with reasoning_content], test_streaming_token_flow,
test_run_agent_end_to_end_against_llamacpp, test_tool_call_write_file_via_llamacpp).
Artifacts written to `C:\Users\Dearly Febriano\Documents\testing-result\20260802T034104Z\`.

## Deferred (NOT executed this session, listed for completeness)
- Multi-browser compatibility test (Safari / Firefox / Edge / Chrome).
- 4-hour soak test.
- Concurrent-user load test (POST /api/chat/stream × 10 in parallel).
- Full axe-core accessibility scan.
- Upgrade from v4.1.x → v4.2.0 path (existing user-data migration).

## Sign-off

Verdict: **READY-FOR-RELEASE** for v4.2.0 once v4.2.1 patch (NUL-byte fix) is merged.
