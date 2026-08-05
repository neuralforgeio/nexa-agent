# Task 0: Fix Critical Bugs — Plan
## Bug A: Version Sync to 4.6.4 | Bug B: Frontend build verification + close-out

**Approved Protocol State** (verified 2026-08-05 via actual filesystem inspection):
| File | Claimed | Actual (main) | Action |
|---|---|---|---|
| pyproject.toml | 4.6.2 | 4.6.2 | → 4.6.4 |
| nexa_web/package.json | 4.2.3 | 4.2.3 | → 4.6.4 |
| config.yaml (version.current) | 4.6.3 | 4.6.3 | → 4.6.4 |
| Duplicate SUGGESTIONS in Composer.tsx | had dup | single declaration (line 30) | already fixed in branch |
| onStop in page.tsx | missing | present (line 270, wired line 410) | already fixed in branch |
| Base pytest | — | 1000 pass / 3 fail / 17 skip | failures pre-existing (main-only, log 4.1.0) |
| nexa --version | 4.6.2 wrong | prints v4.6.2 | → 4.6.4 |
| nexa doctor | — | ALL HEALTHY | confirm pre+post |

Baseline bugs (3 terminal/tool timeouts) are from commit v4.1.0, not within Task 0 scope. Will re-validate post-merge, only gate on `0 NEW failures`.

## Files to touch
1. `pyproject.toml` — bump version 4.6.2 → 4.6.4
2. `nexa_web/package.json` — bump version 4.2.3 → 4.6.4
3. `config.yaml` — bump version 4.6.3 → 4.6.4 + released date
4. `.plans/current_task.md` — this file

## Diffs expected
- 3 lines changed total (version fields)
- zero code logic change
- zero structural change

## Step 6 risk assessment
- Breaking change: none (patch version)
- Backward compat: full
- Tests: no new tests needed (metadata-only patch)

## Step 5 QA gate
- [ ] `pytest tests/ -q` → ≥1003 pass, 0 new failures vs baseline, 3 pre-existing @ terminal tool
- [ ] `npm run lint` (nexa_web) → 0 errors
- [ ] `npm run build` (nexa_web) → success
- [ ] `python -m nexa_cli.main --version` → prints "4.6.4"
- [ ] `python -m nexa_cli.main doctor` → ALL HEALTHY

## Step 7 git flow
1. `git checkout main && git pull origin main`
2. `git checkout -b nexa-demo-task0-v464`
3. commit only Task 0 metadata (not F-* branch files)
4. push branch → merge --no-ff to main → push main → tag v4.6.4 → push tag

## Downstream gates
- Task 0 complete ONLY when: QA pass + merge+push+tag remote-visible.
- F-01 implementation resumes after this tag, per your instruction.
