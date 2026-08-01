# Nexa Agent — Hygiene Procedures (MAESTRO)

A mandatory checklist to run **after any version bump, feature merge, or bug-fix batch**,
before pushing to `main`.

These procedures exist because we learned in v4.1.x that features could accumulate
stale version strings, dead code, and unsynced metadata across many files. Passing
this list keeps the repo consistent.

---

## ✅ Pre-Push Gates (MUST pass)

```powershell
# 1) Backend gates
.venv\Scripts\python.exe -m pytest tests/ -q --tb=no
# Expect: 633+ passed, 0 failed.

# 2) Frontend gates
cd nexa_web
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\eslint.cmd .
.\node_modules\.bin\next.cmd build 2>&1 | tail -20
cd ..

# 3) Version-sanity sweep
# All CURRENT-version files use the version from config.yaml.
# Historical files (worklog.md, .plans/release_body.json, ...) are untouched.
grep -R "v3\.[01]\.0" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.ps1" --include="*.sh" . `
  | grep -v "node_modules" | grep -v "\.venv" | grep -v "\.next" | grep -v "worklog.md" `
  | grep -v "release_body" | grep -v "ROADMAP_20_FEATURES\|v3_launch_plan\|TASK_v4" `
  | grep -v "REAL_INTEGRATION_REPORT"
# Expect: only "introduced in vX" docstrings remain, never "current version = " claims.

# 4) No secrets in commit
git grep "ghp_" . ':!CONTINUATION_PROMPT.md' ':!NEXA_MASTER_PLAN.md' ':!worklog.md'
# Expect: nothing.

# 5) No uncommitted leftovers
git status --porcelain
# Expect: nothing (after the commit).
```

---

## 🔁 Per-Major-Update Checklist (vMajor.Minor.0)

When incrementing MINOR (e.g. 4.1.0 → 4.2.0) or MAJOR (4.x → 5.0.0):

1. **Bump version files (single source of truth)**
   - [ ] `pyproject.toml` → `version = "X.Y.0"`
   - [ ] `nexa_web/package.json` → `"version": "X.Y.0"`

2. **Update the data file** — `config.yaml` is the canonical record.
   - [ ] `version.current` matches pyproject.
   - [ ] `version.released` is today.
   - [ ] `features.{providers,tools_total,agent_modules,...}` refreshed.
   - [ ] `hygiene_watchlist` is accurate (add any new files that brand/version).

3. **Front-door docs refresh**
   - [ ] `README.md` top header matches `config.yaml`.
   - [ ] `SYSTEMPROMPT.md` header version matches.
   - [ ] `CONTINUATION_PROMPT.md` "STATUS PROYEK SAAT INI" matches (current version, tests total, agent-modules count).
   - [ ] `LICENSE` (year/current-version) if a major branding change occurred.

4. **Installer messages**
   - [ ] `scripts/install.ps1` banner shows the new version.
   - [ ] `scripts/install.sh` banner shows the new version.
   - [ ] `docs/MANUAL_TESTING_GUIDE.md` references the new version.

5. **Frontend headers**
   - [ ] `nexa_web/app/page.tsx` EmptyState default `appVersion`.
   - [ ] `nexa_web/components/SandboxPanel.tsx`, `WorkingProcess.tsx`, `SettingsPanel.tsx`,
         `Sidebar.tsx`, `Markdown.tsx`, `MessageBubble.tsx`, `Composer.tsx` — header
         docstring version tag.

6. **Worklog**
   - [ ] Append a new `## Task ID:` entry to `worklog.md` covering this release.
   - [ ] Release notes drafted in `.plans/release_body.json`.

7. **Branch / tag / release**
   - [ ] Demo branch `nexa-demo-<8-hex>` exists locally and has been pushed.
   - [ ] `git checkout main`
   - [ ] `git merge --no-ff nexa-demo-<8-hex> -m "..."`
   - [ ] `git tag -a vX.Y.0 -m "Nexa Agent vX.Y.0 — <headline>"`
   - [ ] `git push origin main vX.Y.0`
   - [ ] GitHub Release created from the tag (via `gh` or the curl recipe in
         `CONTINUATION_PROMPT.md`).
   - [ ] The previous demo branch is kept (never force-deleted).

---

## 💡 Per-Patch Checklist (v4.1.0 → v4.1.6)

When incrementing PATCH only (bug fix, no feature changes):

- [ ] `pyproject.toml` and `nexa_web/package.json` bumped.
- [ ] `config.yaml` `version.current` bumped.
- [ ] Brief "What's fixed" bullet appended to `SYSTEMPROMPT.md` version history.
- [ ] Testsuite runs green (633+ pass).
- [ ] Demo branch + PR merged to main; tag + push.

---

## 🧹 Per-Repository-Cleanup Checklist (ad-hoc)

Run when the workspace feels "dusty":

- [ ] `git status` clean (no stray ``*.bak``, `*.tmp`, `*.nexa.tmp`).
- [ ] Dead exports removed from `nexa_web/lib/theme.ts` (or marked with `# reserved for v5`).
- [ ] Unused components removed from `nexa_web/components/`.
- [ ] Docstrings include a version-first-appearance comment if the module is ≤ 1 release old.

---

## 🧠 Author Note

If any step in this checklist **fails**, do not push to `main`. Either:
- Fix the underlying issue, OR
- Document why you are choosing to ship with the known issue (rare, and
  only with an explicit `[skip-hygiene]` tag in the commit message).
