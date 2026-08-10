# Task: QA-VERIFY-v511 — Verify GLM-5.2 v5.1.1 report (25 items)

Task ID: QA-VERIFY-v511
Mode: READ-ONLY verification (no fixes unless explicitly approved). Follows QA v5.1.1 report.
HEAD: 44a927c (v5.1.1). Suite baseline this env: 1127 passed / 13 skipped / 0 failed (== 1130 logical? verify below).

## Objective
Independently verify: 13 FIXED still hold; 1 PARTIAL (nexa submodule shims) reproduced; 9 test-side
failures characterized (OS-specific), + baseline/pytest counts. Output CONFIRMED/DISPUTED/NME per claim.

## Key verification targets (evidence needed)
- PARTIAL-1: nexa/__init__.py present but missing nexa.config / nexa.constants submodule shims.
- C group: the 9 "test-side" failures are Linux/Windows OS-specific assertion bugs (confirm: pass on Win?).
- Group A fixed IDs: confirm via static greps + behavior runs (no regressions to ours).
- Baseline: reconcile "1130 logical tests here" vs QA's "1147 collected / 1120 pass / 10 fail" on Linux.

## Non-goals
- No new fixes in this pass (verification only). Remediation is a separate authorized task.
