# Task: REL-v5.1.1 — Release ceremony (Section 17 iron law)

Task ID: REL-v5.1.1
Agent: OpenCode (kimi-k3) — SOP/Protocol v9 (Apex)
Timestamp: 2026-08-10
Mode: S9 RELEASING (authorized via "gas A, B, C")
Baseline: HEAD=2d0659c; suite `1127 passed, 13 skipped, 0 failed`; git clean; remote main==2d0659c.

## 1. Objective
Publish PATCH release v5.1.1 for the two QA fix groups (grp1 + grp2): bump 4 manifests to 5.1.1,
update README if needed, commit, annotated tag, push, gh release create + verify parity.

## 2. Impact table (Step 8 of Workflow)
- Changes: CLI/TUI/WS/provider/sandbox bug fixes + read-only handlers + compat shim.
- SemVer: PATCH (backward-compatible bug fixes; no breaking API/schema).

## 3. Scope (exact files to modify)
- pyproject.toml, package.json, openforge_web/package.json, config.yaml  -> version 5.1.0 -> 5.1.1
- README.md (Rule C-2) -> ONLY if it advertises a stale version/badge or removed feature. Verify first.
- CHANGELOG/release notes -> gh release notes (angry-3AM tone: what broke, what to do).
- No source-code changes in this release commit.

## 4. Non-Goals
- No new features; no extra fixes; no refactors. Release only.
- Do not delete tags/releases (no force-push). If parity breaks mid-ceremony -> Section 17.8 recovery + HALT.

## 5. Baseline & evidence anchors
- HEAD=2d0659c; remote tags: v5.0.3..v5.1.0 published (verified). Latest gh release: v5.1.0.
- Suite green: 1127/0-failed. Build: py_compile rc=0 on all touched files. gh.exe at C:\Program Files\GitHub CLI\gh.exe.

## 6. Release ceremony (Section 17.4 sequence)
1. SYNC: git clean; remote in sync (verify).
2. GATE SWEEP: suites already green this session; re-confirm compile + key tests.
3. VERSION: pyproject/package/openforge_web/package/config.yaml -> 5.1.1 (all four agree).
4. CHANGELOG: gh release notes (markdown) — no in-repo CHANGELOG file maintained? verify.
5. COMMIT: chore(release): v5.1.1 with manifest bumps.
6. TAG: git tag -a v5.1.1 -m "what|why|risk: LOW (patch, backward-compatible bugfix)".
7. PUSH: git push origin main && git push origin v5.1.1.
8. RELEASE: gh release create v5.1.1 --title ... --notes <3AM-friendly notes>.
9. PUBLISH: not a draft (auto-published).
10. VERIFY: gh release view v5.1.1; gh api releases/tags/v5.1.1; git ls-remote --tags | grep v5.1.1.
11. ANNOUNCE: worklog links release URL only after verification.

## 7. Parity & artifacts
- Assets: source-only release (this project distributes via git/pip editable), so no binary checksums needed.
  Notes will state that. If assets present, checksum them.

## 8. Rollback (before publish only)
- If anything fails pre-publish: local tag delete + reset the release commit (no remote harm). If mid-publish fails: 17.8 recovery (create release for pushed tag, or escalate if tag/release mismatch).

## 9. Abortion Criteria
- gh auth/network failure mid-ceremony -> HALT (S12) and report partial state; do NOT claim release done.
- Any gate failure -> Step 7 remediation (max 3), else escalate.

## 10. Knowledge Artifacts
- worklog.md entry with verified release URL + tag SHA + verification commands.
- .plans/qa/QA-VERIFICATION-v503.md: add a release reference line mapping fixed IDs -> v5.1.1.
- Clear .plans/active_tasks.md lease.
