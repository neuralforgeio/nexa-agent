# schedule_tasks.md — OpenForge Autonomous Cron Schedule (Z.ai / GLM-5.2)

> **Purpose.** Run OpenForge as a self-healing, self-improving project during the owner's
> absence (boarding school, ~3 months, no regular laptop access). Source of truth for cadences,
> task prompts, safety rails, persistence contract, and audit telemetry.
>
> **Mandatory SOP.** Every cron run MUST operate under **SOP Prompt Mandatory v9 (Apex Edition)**,
> which the operator pastes into the Z.ai cron form **separately**. Do **not** inline it here.
> A canonical copy is kept at `.sop/UNIVERSAL_AUTONOMOUS_DEVELOPMENT_PROTOCOL_v9.md` in this repo.
>
> **Truth sources (read at the start of every run):**
> `worklog.md` (append-only history) · `git log -1` · `git status --porcelain` ·
> `.plans/context_checkpoint.md` · `.plans/active_tasks.md` · `.plans/agent_log.md` · `.plans/qa/*.md`.
>
> **Forge data root:** `$HOME/.openforge` (never commit its contents).

---

## 0. Shared Block — paste BEFORE any cadence prompt
*(Tiny prelude: platform mapping + immutables. Keep it to a few lines.)*

```text
You are the OpenForge autonomous engineering agent. Read AGENTS.md, then read:
- .sop/UNIVERSAL_AUTONOMOUS_DEVELOPMENT_PROTOCOL_v9.md  (THE SOP — referenced, not inline)
- worklog.md (tail -40) and .plans/context_checkpoint.md (resume/discard stale explicitly)
- .plans/active_tasks.md and .plans/agent_log.md (coordination + leases, Section 16)

Platform mapping (record in plan): build=setuptools/pip -e . · test=pytest · lint/format/typecheck=none wired
(git+CI via GitHub Actions) · release=git tag + gh release (Section 17 iron law) · manifests:
pyproject.toml, package.json, openforge_web/package.json, config.yaml (versions MUST agree, Section 2 Step 8).

Immutables: bug-hunt is the default state; Triad Verification Gate 3/3 before any claim; no tag without a
verified published Release (Section 17 P7); worklog is append-only; write .plans/context_checkpoint.md on
completion; on any doubt between act vs ask → do the Safer thing (no-op) and log it for the human.
```

---

## Cadence QA-Q — Quick QA, read-only · every 4 hours
**Cron:** `0 */4 * * *` · **Est:** ~10 min · **Subagents:** 3 (QA Hunter · Test Runner · Reviewer)

```text
Task: OpenForge AUTONOMOUS Quick QA (QA-Q). Read-only audit. Do NOT commit.

Mandates (non-negotiable):
1) Bug hunt is the CURRENT default state. Re-verify the newest known-broken items from worklog.
2) Verification is mandatory for ANY claim (Triad 3/3: execute it, show the output, search for counter-evidence).

Do, in order:
 A. Pre-flight & context
    - If /tmp/openforge-cron.lock exists → append .plans/agent_log.md INFO "skip: lock present" and exit 0.
      Else create it (remove at the end, even on error).
    - Read .sop/UNIVERSAL_AUTONOMOUS_DEVELOPMENT_PROTOCOL_v9.md (it governs this run).
    - Read: tail -40 worklog.md; git log --oneline -10; git status --porcelain;
            .plans/context_checkpoint.md; .plans/active_tasks.md; .plans/qa/*.md.
 B. Spawn 3 subagents in PARALLEL (Task tool):
    1) QA Hunter: scan for NEW P0/P1 symptoms (imports, dispatch tables, unannotated WS handlers,
       missing exports) using rg + reads; re-open .plans/qa/QA-VERIFICATION-*.md and re-verify the 3 most
       recent FIXED items are still true (print file:line + the exact snippet that proves it).
    2) Test Runner: run `python -m pytest tests/ -q --ignore=tests/test_llamacpp_real.py --no-header -p no:cacheprovider`.
       Capture tail. Then smoke: `python -m openforge_cli.main --version`, `... doctor`,
       `... update --help`, `... rollback --list`, `... gateway --help`.
    3) Reviewer: inspect `git diff HEAD~1..HEAD --stat` and read the actual diff; report code-vs-intent
       risks, TODO/debug leftovers, accidental deletions.
 C. Decide (deterministic):
    - If ANY P0/P1 NEW or regression is PROVEN with quoted output → mark it prominently and append worklog
      entry with type QA-Q-BLOCKER. Exit 1 (signals the scheduler a bug is outstanding for FIX-C).
    - Else → append worklog entry QA-Q-OK summarizing: pytest counts, smoke results, review conclusion.
 D. Persistence: append .plans/agent_log.md INFO QA-Q; write .plans/context_checkpoint.md (FSM S10) with
    evidence anchors (commands + outputs). Release the lock file.

Output: report findings only. No fixes, no commits, no releases here.
```

---

## Cadence FIX-C — Deep Fix Cycle · every 8 hours
**Cron:** `0 2,10,18 * * *` · **Est:** ~25–35 min · **Subagents:** 4–5 (QA Hunter · Code Reviewer · Test Runner · Verifier [+ Explorer: OFF])

```text
Task: OpenForge AUTONOMOUS Fix Cycle (FIX-C). Fix outstanding defects first; only then small improvements.

Non-negotiables:
- Fix > Feature. If ANY confirmed P0/P1 exists (from prior QA-Q/worklog or this run's QA Hunter) → you MUST
  fix up to 2 of the highest-severity items BEFORE anything else.
- No destructive action by default; never delete data; update only after a snapshot.
- Triad 3/3 before ANY claimed "fixed". No claim below 3/3.

Do, in order (FSM S1→S10):
 A. Pre-flight & context — same as QA-Q (lock, SOP, worklog tail, git log/status, checkpoint, leases).
 B. Reproduce & boundary-read: for each candidate bug, capture the exact failing output (verbatim) and the
    smallest file:line anchor. Build `.plans/current_task.md` (Objective/Scope/Non-Goals/Baseline/Risk/
    Rollback). Run Step-1 pre-mortem (predict the incident, then revise the plan until no unaddressed mode).
 C. Spawn 4 subagents in PARALLEL:
    1) QA Hunter: confirm the defect list (P0/P1 first), find NEW blockers, and VERIFY the top-2 are real.
    2) Code Reviewer: review the diff you intend to make (write it first as a plan); look for the nine
       cardinal sins of anti-hallucination, incorrect imports/annotations, hidden side effects.
    3) Test Runner: run the focused tests for those bugs AND the broader regression files
       (tests/test_cli_dispatch_regression.py, tests/test_grp2_fixes.py, tests/test_v512_guards.py,
        tests/test_category9.py).
    4) Verifier: dry-run the Triad gate on every proposed fix; require 3/3 before claiming in worklog.
 D. Implement minimal-diffs (Step 3). For EACH bug: add a regression test that FAILS without the fix and
    PASSES with it (prove it by a temporary revert if feasible).
 E. Gates (must all pass; else S8 ≤3 attempts then revert the smallest hunk and log):
    - `python -m py_compile` every touched file → rc=0.
    - full: `python -m pytest tests/ -q --ignore=tests/test_llamacpp_real.py --no-header -p no:cacheprovider`
      → expect ≥1127 passed, 0 failed (or equal/better than the baseline recorded in .plans/current_task.md).
    - smoke: openforge --version · doctor · gateway --help · update & --help · rollback --list.
    - import: `python -c "import nexa, openforge; print('OK')"`.
 F. Decision (deterministic):
    - If ALL green → Version: bugfix-only ⇒ PATCH bump; else MINOR; MAJOR otonom dilarang. Update the four
      manifests to the target version. Commit + PUSH (atomic, conventional). If a release is warranted by
      project policy for this change set → execute Section 17 ceremony with verification battery.
    - If ANY gate fails → revert the smallest offending hunk(s), re-run the FULL suite, and either retry
      (≤3 total iterations) or HALT: revert everything, append `[CRON-CRASH]` worklog entry, exit non-zero.
 G. Persistence: worklog append (requirement template below), .plans/agent_log.md INFO/WARN,
    .plans/context_checkpoint.md with evidence anchors. Release lock. exit 0 on success.

Definition of a verified fix (required fields per bug): failing-output BEFORE · minimal repro · fix evidence
AFTER (quoted) · regression test name · triad=3/3.
```

---

## Cadence AUDIT-F — Full Audit (+ autonomous feature when clean) · every 24 hours
**Cron:** `0 3 * * *` · **Est:** ~40–50 min · **Subagents:** 5 (adds Feature Explorer)

```text
Task: OpenForge AUTONOMOUS Daily Audit (AUDIT-F). Comprehensive re-verification; if zero P0/P1 remain,
allow ONE small user-friendly feature (see Feature Constraints).

Do, in order:
 A. Pre-flight & context — identical to QA-Q/FIX-C. Read AGENTS.md, SOP v9 (referenced), worklog tail,
    git log -20, git status, .plans/context_checkpoint.md, .plans/active_tasks.md, .plans/qa/*.md.
 B. Spawn 5 subagents in PARALLEL:
    1) QA Hunter: re-verify ALL open items from QA-VERIFICATION-* and any [CRON-CRASH]/P0/P1 history.
       Produce a table: id, file:line, current status (CONFIRMED-FIXED / REOPENED evidence), quoted output.
    2) Code Reviewer: review last 24h diffs (git log --since="24 hours ago" --stat + focused reads).
    3) Test Runner: run the FULL pytest suite (no llama.cpp gating) AND every fired smoke/import test.
       Report counts verbatim.
    4) Verifier: run the Explicit Triad Verification — every fixed claim has direct output, structural
       proof, and a negative search. Flag anything <3/3.
    5) Feature Explorer (ONLY if QA Hunter shows zero P0/P1 REOPENED): propose ≤2 small user-awam
       improvements with a tiny ADR sketch each, impact estimate, and tests-to-write. DO NOT implement.
 C. Decision (deterministic):
    - If ANY P0/P1 REOPENED → treat as FIX-C but with the single highest-severity item only; follow FIX-C
      gates; version = PATCH.
    - Else → optionally implement ONE (1) approved-by-logic feature (lowest risk, clearest user win) with
      tests; version = MINOR. Details must satisfy: no existing behavior change, explicit docstring/help.
 D. Gates: identical to FIX-C. Commit + push when all green. If releasing is appropriate (new feature),
    run the Section 17 ceremony: tag → gh release create → independent verification battery.
 E. Persistence: worklog (full template), agent_log INFO, context_checkpoint.md, and write the daily
    QA status file to .plans/qa/ (may overwrite QA-<date>.md), then release lock and exit 0.

ROLLOVER rule: if audit time-box would exceed the run window STOP at the Verifier stage, finish the
reconciliation, note "partial audit" with evidence, and exit 0. Never leave a dangling mutated tree.
```

---

## Worklog Append Template (use at the END of every run — append ONLY)
```markdown
---
Task ID: CRON-<YYYYMMDDHHmm>-<4h|8h|24h>
Agent: GLM-5.2 cron run
Started: <ISO>  Ended: <ISO>  Duration: <N>min
Work Log:
- <steps + subagent results, verbatim outputs for gates>
Bugs Found: [id · severity · file:line · quoted symptom]
Bugs Fixed: [id · commit]
Regressions: [none | list + quoted output]
Features Added (autonomous): [none — P0/P1 outstanding | one item + tests]
Verification Gate: pytest=<p>/<t> (skip=<s>) · smoke=PASS · import=PASS · Triad=3/3
Git: <commit-hash or "no changes — no P0/P1, no feature chosen">
Stage Summary: <1-3 sentences>
```

---

## Standby / Do-Not rules (cron-mode guardrails)
- Never force-push; never delete or move existing tags/releases; never auto-MAJOR. (Section 17.10)
- Never store secrets or FORGE_HOME data in the repo; never log secrets/tokens.
- Always leave the tree clean; on any failure → revert your own changes before exiting.
- Keep `.plans/*` concise, factual, evidence-anchored; write in the same tone as existing worklog.
- If SOP v9 and a past habit conflict → SOP v9 wins; surface the conflict in `.plans/agent_log.md` (ERROR) and stop the dependent part.

---

## Health check (how the human reads this from a phone)
1) `gh release list` → Latest = the newest vX.Y.Z; 2) `tail -20 worklog.md` → last run shows gates green;
3) `git log -1` → a commit from the last 24h or a clear "no changes" note. Anything else → investigate.
