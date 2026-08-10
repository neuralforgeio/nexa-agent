# Task: FIX-QA-P0-CLI-GRP1 — Repair tier-1 defects from QA verification (group no. 1)

Task ID: FIX-QA-P0-CLI-GRP1
Agent: OpenCode (kimi-k3) — SOP/Protocol v9 (Apex)
Timestamp: 2026-08-10
Maturity: Production | Platform: Windows dev box / cross-platform code
Mode: S5/S6 WRITE (authorized by user selecting "no. 1")

## 1. Objective
Fix the highest-impact, CLI/TUI-breaking defects confirmed in QA-VERIFY-v503, group "no. 1":
restore working `update`/`rollback`/`doctor` subcommands, remove duplicate doctor, restore
gateway symlink, and honor the nexa-shim mandate decision (deferred — see Non-Goals).

## 2. Exact bug list to fix (from QA-VERIFICATION-v503.md)
- P1-X1  REGRESSION : `_cmd_update` / `_cmd_rollback` referenced in dispatch but undefined -> NameError.
- P0-4   STILL-BRK  : `openforge doctor` not in dispatch table -> prints help instead of HealthReport.
- P1-15  STILL-BRK  : `_cmd_doctor` defined twice (main.py:505 AND :577); second shadows first.
- P1-X2  REGRESS-adj: doctor LOCK-integrity claim is unrealized (fixed transitively by P0-4 wiring).
- P0-2   REGRESSION : install.sh symlink loop drops `openforge-gateway` (adds `openforge-tui`).

## 3. Scope (exact files to modify)
- openforge_cli/main.py      -> merge/keep ONE _cmd_doctor; add "doctor" dispatch branch; define _cmd_update + _cmd_rollback.
- scripts/install/install.sh  -> re-add `openforge-gateway` to symlink loop (keep openforge-tui).
NO other source files. No dependency edits.

## 4. Non-Goals (verified unchanged at end)
- Do NOT fix the remaining confirmed defects (P0-5 WS annotation, P0-6 TUI chat, P0-7 nexa shim,
  P1-7..P1-12). Those belong to later authorized groups.
- Do NOT bump version, tag, or release (fix-only; release is a separate authorized step).
- Do NOT touch tests semantics; add only a focused regression test for P1-X1 (dispatch functions exist).
- Do NOT modify public API beyond restoring intended behavior of existing commands.

## 5. Baseline Snapshot (captured this session)
- HEAD: 144989a (v5.0.3 code surface; local tag v5.1.0 manifests-only diff).
- pytest baseline this env: 1112 passed, 13 skipped, 0 failed (158.61s).
- `git status`: clean at start. Reference: QA-VERIFICATION file .plans/qa/QA-VERIFICATION-v503.md.

## 6. Impact Radius
- openforge_cli/main.py: main() dispatch + 3 command impls; imported by openforge console-script.
- install.sh: affects fresh installs only (symlink set). No runtime code change.

## 7. Contract Stability
- Restores documented CLI commands (update/rollback/doctor). Not a breaking change. No schema/API change.

## 8. Test Strategy
- Regression (P1-X1/P0-4/P1-15): unit test asserting `_cmd_update`, `_cmd_rollback`, single `_cmd_doctor`,
  and that dispatch map routes "doctor" (assert source contains branch + callable exists).
- Behavior: run `openforge doctor`, `openforge update --help`? (update has no --help in current parser; run
  `openforge update` expecting a real result code, not NameError) after fix.
- Full suite: re-run pytest to confirm no regressions (compare against 1112-pass baseline).
- install.sh: static re-check line containing the 5-binary loop.

## 9. Rollback Strategy
- `git checkout -- openforge_cli/main.py scripts/install/install.sh` (+ remove the new test file if added). <5 min, no data loss.

## 10. Risk Assessment
- _cmd_update/_cmd_rollback need a sane implementation. Minimal-risk choice: implement read-only status/inspect
  behavior (list current version / available backups; refuse mutation without explicit flags) to avoid executing
  network/git mutations during a bugfix commit. [I] matches existing CLI tone (migrate is conservative).
- doctor dispatch: low risk; wires existing SelfHealth.run_full_check already used elsewhere.
- Duplicate doctor removal: keep the richer v5.1.0 variant (577, docstring mentions LOCK integrity) OR merge; removing
  a duplicated def has no external contract change. [E-verified bodies are equivalent except docstring.]
- Edit tools on Windows with indentation: use exact-match edits on small hunks only.

## 11. Abortion Criteria
- Full pytest suite drops below 1112 passed after edits -> revert.
- `_cmd_update`/`_cmd_rollback` cannot be implemented without network/git mutation -> implement read-only safe versions.

## 12. Release Strategy Preview
- NONE now. After this fix lands + full suite green, the NEXT user-authorized step would be a PATCH release (v5.1.1) with tag+release per Section 17 iron law. Logged here as the plan's decision.

## 13. Knowledge Artifacts
- New focused test file (tests/test_cli_dispatch_regression.py) OR extend existing; verify which harness exists first.
- Update .plans/qa/QA-VERIFICATION-v503.md statuses to FIXED for these IDs after verification.
- worklog.md append.

## 14. Release parity
- No tag created in this task -> no parity check needed. If later released, execute Section 17 in full.
