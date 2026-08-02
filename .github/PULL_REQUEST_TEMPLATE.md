# Pull Request — Nexa Agent

<!--
Thanks for the contribution. PRs that fail the hygiene checklist will be asked
to rebase. Use the body below to make your intent explicit.
-->

## Description

<!--
A short (1-3 sentence) summary of the change. End with `Fixes #<issue-id>` if
applicable.
-->

## Type

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 🔄 Improvement / refactor
- [ ] 📦 Dependency bump
- [ ] 📚 Documentation
- [ ] 🧪 Test-only change
- [ ] 🔒 Security fix
- [ ] 🎨 Style / formatting

## Changes in this PR

<!--
Bullet list of the actual code changes. Keep it ~5 items; deeper context goes
in worklog.md.
-->

-
-
-

## Verification performed

- [ ] `pytest tests/ -q --tb=no` — all tests pass
- [ ] `cd nexa_web && ./node_modules/.bin/eslint.cmd .` — clean
- [ ] `cd nexa_web && ./node_modules/.bin/next.cmd build` — clean
- [ ] Manual run against a live provider / local server (describe below)
- [ ] I have re-run the relevant `tests/test_<feature>.py` for any change
      that touches a tool

### Live verification notes

<!-- Optional: describe what you ran + the observable outcome. -->

## Checklist

- [ ] Branch is `nexa-demo-<8-hex>` (pushed), not `main`.
- [ ] Tests added for new behavior; existing tests updated when semantics change.
- [ ] No secrets or credentials in the diff.
- [ ] No changes to the frozen-history files:
      - `worklog.md` (append-only)
      - `.plans/release_body.json`
      - `.plans/ROADMAP_20_FEATURES.md`
      - `.plans/v3_launch_plan.md`
      - `.plans/TASK_v4_PUNCHLIST.md`
- [ ] Version bumped appropriately (MAJOR.MINOR.PATCH per `config.yaml`).
- [ ] Tag and GitHub Release scripts prepared (will be executed by maintainers).
