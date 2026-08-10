# QA VERIFICATION REPORT — GLM-5.2 v5.1.1 Bug Report (25 items)
# Independently verified by OpenCode (kimi-k3) — SOP v9 compliant

Verifier env: Windows 11, Python 3.13.3, HEAD=44a927c (v5.1.1 released).
QA env (claimed): Linux py3.12, v5.1.1 (44a927c). Same commit => same code under test.
Parity proof: tag v5.1.1^{} = 44a927c = remote main HEAD (verified earlier).

Legend: CONFIRMED / DISPUTED / NME.

## A. FIXED bugs (13) — all CONFIRMED on this env
| FIX | claim | verdict | evidence (verbatim) |
|-----|-------|---------|---------------------|
| FIX-1 | doctor dispatch + single def | CONFIRMED | `def _cmd_doctor` count=1; `args.command == "doctor"` at main.py:162; `openforge doctor` prints HealthReport, exit 0. |
| FIX-2 | WS `: WebSocket` annotation | CONFIRMED | server.py:1029 + :1244 annotated. live uvicorn: both `/ws/terminal` and `/ws/approval` CONNECTED. |
| FIX-3 | TUI chat render | CONFIRMED | layout.py:85 `layout["chat"].update(render_chat_area(state))`. |
| FIX-4 | gateway symlink restored | CONFIRMED | install.sh:151 loop lists all 5 binaries incl openforge-gateway. |
| FIX-5 | update/rollback/migrate dispatch | CONFIRMED | functions exist; `update`, `rollback`, `migrate` exit cleanly. |
| FIX-6 | skills ERROR import | CONFIRMED | skills_panel.py:22 imports ERROR from theme. |
| FIX-7 | provider chat_stream error tuple | CONFIRMED | provider.py:224-228 wraps _get_client in try/except -> yields ('error', ...). |
| FIX-8 | PersonaBadge.detail_open | CONFIRMED | state.py:48 `detail_open: bool = False`. |
| FIX-9 | /exit /quit dispatch | CONFIRMED | commands.py:421-422 entries; app.py:237 checks quit_requested. |
| FIX-10 | sandbox timeout clamp | CONFIRMED | server.py:1624 `timeout=min(180.0, MAX_TIMEOUT)`. |
| FIX-11 | ws_approval auth | CONFIRMED | server.py:1247-1251 calls verify_token_ws before accept. |
| FIX-12 | doctor de-duplicated | CONFIRMED | exactly one def. |
| FIX-13 | live WS connection test | CONFIRMED | both endpoints CONNECTED locally. |

## B. PARTIAL (1) — CONFIRMED
| ID | claim | verdict | evidence |
|----|-------|---------|----------|
| PARTIAL-1 | nexa shim top-level works, submodules missing | CONFIRMED | `import nexa` -> OK (5.1.1, DeprecationWarning). `from nexa.config import FORGE_HOME` -> ModuleNotFoundError. `from nexa.constants import FORGE_NAME` -> ModuleNotFoundError. Only __init__.py exists; no config/constants submodule shims. |

## C. Test-side failures (9) — CONFIRMED as OS-specific, NOT production bugs
| items | claim | verdict | evidence |
|-------|-------|---------|----------|
| TEST-1..3, TEST-4, TEST-5..9 | Linux-only failures, loose assertions / Windows-only commands | CONFIRMED as test-side | On Windows (this env): all 38 targeted tests PASS. QA's own root-cause notes (substring "python3" vs "python3.12"; POSIX has no `type`; `\\` not collapsed on Linux) match file contents. Production code unaffected. |

## D. Baseline reconciliation
- My collect: **1140** collected (vs QA 1147 on Linux) — env-gated/skip-marked files differ; consistent with cross-OS delta.
- My full run (Win): **1127 passed, 13 skipped, 0 failed**. QA (Linux): 1120 passed, 10 failed. Delta is the 9 OS-specific test-side failures (+1 parametrized variant).
- DISPUTED on absolute counts (env), CONFIRMED on root-cause classification.

## Overall verdict about the QA report
- 13 FIXED: CONFIRMED.
- 1 PARTIAL (nexa submodule shims): CONFIRMED — an easy follow-up fix if desired.
- 9 test-side: CONFIRMED as test-side, NOT production bugs.
- No DISPUTED on production behavior. No new regressions found by this verification.
