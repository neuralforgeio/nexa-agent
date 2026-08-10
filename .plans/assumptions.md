# Assumptions Ledger — QA-VERIFY-v503

- A1: pytest suite is runnable locally in .\.venv on Windows/py3.13. Risk: if runner errors
  on OS-specific tests, some pytest claims become OS-UNVERIFIABLE. Verify by running.
- A2: bash/git-bash availability for install.sh static checks is NOT required; static line
  reads suffice to CONFIRM/DISPUTE file-content claims (P0-1, P0-2, P1-13).
- A3: Live-network/agent tests (TUI render, WS auth) may be infeasible to fully exercise on
  this box; where a live proof is impossible, verdict = NEEDS-MORE-EVIDENCE with static evidence.
- A4: Local HEAD 144989a code == QA-tested d93319a code for all non-manifest files
  (supported by git diff --stat showing only manifests).
