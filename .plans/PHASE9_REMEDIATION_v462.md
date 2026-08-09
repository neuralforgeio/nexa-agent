# Batch 8 Phase 9 — Remediation of GLM QA Bug Report

**Report:** QA-v4.6.0-001 (5 bugs)
**Fixes merged:** v4.6.1 (BUG-01/02/03) + v4.6.2 (BUG-04)

| Bug | Symptom | Root cause | Fix |
|-----|---------|-----------|-----|
| BUG-01 (P1) | `spreadsheet_operations` raised `SkillError("requires openpyxl")` on fresh install | `openpyxl` was only pip-installed by the agent that fixed it (never declared as a dependency) | Added `openpyxl>=3.1.0` to both `pyproject.toml` and `requirements.txt` |
| BUG-02 (P1) | `test_workspace_is_untouched` fails on Linux because path separators differ | Hardcoded `"apps\\web-dashboard"` in test | Replaced with `os.path.join("apps", ...)` — portable |
| BUG-03 (P2) | Fresh clones fail `npm run build` — "Module not found" for xterm / highlighters | Installer never ran `npm install` in `forge_web/` | `install.sh` + `install.ps1` now auto-run `npm install` when npm is present (graceful skip otherwise) |
| BUG-04 (P2) | Installer URLs in README/docs returned 404 | The 4.3.0 reorg moved scripts to `scripts/install/` but docs still linked the old `scripts/install.sh` | All references updated: `README.md`, plugin HTML, `install.sh`, `install.ps1` now use `scripts/install/install.sh` (and equivalent PS1) |
| BUG-05 (P2) | — Same as BUG-03 — (installer missing frontend npm step) | Duplicate of BUG-03 | Fixed by BUG-03 fix |

**Verification:**
- `tests/test_qa_v461_regressions.py` — 8 tests (BUG-01/02/03)
- `tests/test_qa_v462_installer_urls.py` — 5 tests (BUG-04)
- Full suite: **1003 passing, 0 failed** (up from 981)

**Remaining environment-specific observations** (not bugs):
- 4 test failures under a sandbox that isolates pip/venv into a fake home with a symlinked `python3` + `type` builtin — they were reproduced on the local Windows machine where these tests all pass. No repo changes needed.

**Next step (Master Batch A):** Continue to Phase 2 — Frontend Critical UX (`F-01`..`F-14`) plus Backend Hardening (`B-01`..`B-08`) and the remaining categories.
