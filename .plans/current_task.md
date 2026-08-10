# Task: REL-v5.1.2 — D1 full-compat nexa shim + D2 actionable update/rollback + D3 test-portability + defects

Task ID: REL-v5.1.2  (covers D1, D2, D3 + remediation of remaining defects)
Agent: OpenCode (kimi-k3) — SOP/Protocol v9
Timestamp: 2026-08-10
Mode: WRITE (authorized: "gas ... langsung kerjakan yang terbaik")
Baseline: HEAD=25f8334 (v5.1.1). Suite green 1127/0-fail earlier this session.

## Scope (exact)
D1: nexa/config.py + nexa/constants.py submodule shims; extend regression tests.
D2: openforge_cli/main.py — make _cmd_update perform a SAFE offline git-update of
    FORGE_HOME/lib (origin/main snapshot -> .versions/<sha> backup -> fast-forward pull ->
    rewrite LOCK) DRY when working tree dirty or offline; _cmd_rollback[to_version] restores
    a named snapshot -> rewrite LOCK; both refuse destructive action without explicit state.
D3: tests/test_category9.py, tests/test_terminal_tool.py, tests/test_*hardened*.py —
    parametrize OS-specific assertions/commands; use sys.executable-aware assertions; keep
    behavior identical.
Defects: none outstanding for production per QA v5.1.1 (PARTIAL-1 covered under D1).
Non-goals: no features beyond D1-D3; no release/platform changes besides version bump artifacts.

## Evidence anchors
- QA PARTIAL-1: nexa config/constants ModuleNotFoundError (verified) — fix by submodule shims.
- D2 minimal: FORGE_HOME/lib is a git checkout of origin/main (install.sh clones it);
  update = snapshot -> fetch -> pull --ff-only -> write_lock; rollback = choose snapshot under
  .versions -> copytree -> write_lock. Non-destructive default; require --to to actually restore.
- D3: pytest run earlier in this env showed 38/38 PASS on Windows; the 9 QA failures are Linux-side
  test assertions — fix portability.

## Rollback plan
- git checkout of modified sources + delete new test/shim files (D1) -> all reversible <5m.

## Release plan
- PATCH v5.1.2 (Section 17) 4-manifest + README sync, tag, gh release, parity verify.
