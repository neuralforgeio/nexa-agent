# 🔨 OPENFORGE REFACTOR — MASTER PLAN
## The Great Consolidation: Rename + Unified Architecture + UI/UX Evolution

> **Task ID:** `OPENFORGE-REFACTOR-PLAN`
> **Author-agent:** Principal Engineer (Protocol v8 + Forge Amandemen v1)
> **Date:** 2026-08-08
> **Status:** S3 PLANNING — awaiting user approval gate (S5)
> **Precedence note:** User instruction (this prompt) overrides SOP default.
> The rename is user-designated **MINOR (v4.11.x → v4.12.0)** on the premise that
> the migration layer makes the transition backward-compatible from the USER's
> perspective (auto-migrate), even though it is API/path-breaking internally.
> This deviation from strict SemVer is logged here explicitly per P5.

---

## ⚠️ SECTION 0 — FORMAL RISK NOTE (read before approving)

| Item | Assessment | Evidence |
|------|-----------|----------|
| Rename total (207 `.py` + folder + env) | **API/path-breaking internally.** Strict SemVer would classify MAJOR. | `git grep -il forge` = 342 files; 208 `.py` |
| Why allowed as MINOR here | User explicitly and repeatedly designated it MINOR, and mandated an **auto-migration layer** (`openforge migrate`) that preserves user data → backward-compatible *from the user's seat*. | Contradiction Resolution order #2 (human instruction) |
| Residual risk | External consumers importing `forge` as a Python package, or relying on `FORGE_*` env vars / CLI binary names, WILL break unless a compat shim ships. | structural |
| Mitigation decision needed | **Ship a temporary compatibility shim** (`forge` → `openforge` re-export package + `FORGE_*` env fallback, marked deprecated) for at least one minor cycle — keeps the MINOR claim honest. If you refuse the shim, this is genuinely a MAJOR. | pending |

---

## 🗺️ SECTION 1 — TOPOLOGY & EVIDENCE MAP

| Domain | Fact | Tag |
|--------|------|-----|
| Files containing `forge` (case-insensitive) | 342 files | [E] |
| `.py` files touched | 208 | [E] |
| Top dirs with `forge` refs | skills(80), tests(68), agent(37), forge_web(31), .plans(23), tools(23), forge(16), ui_tui(14) | [E] |
| Python packages to rename | `forge/` → `openforge/`, `forge_cli/` → `openforge_cli/` | [E] |
| Frontend folder | `forge_web/` → `openforge_web/` | [E] |
| Version sources (must sync) | pyproject.toml(=4.15.2), package.json, forge_web/package.json, config.yaml(**4.15.0 — stale, will fix**) | [E] |
| Tools / Skills / Agent modules / Providers | 85 tools / 44 skill files / 41 agent modules / providers catalog present | [E] |
| SYSTEMPROMPT.md state | version says **4.6.1**, claims **10 tools** (real: 85+), lines 22-23 malformed, no skills/providers/C6–C9 | [E] |
| Test baseline | pytest 1097 passed / 20 skipped / 0 failed; vitest 80/80 | [E] |
| llama.cpp local | UP on 127.0.0.1:8080, `--jinja` enforced | [E] |

**Maturity:** Production (full CI + releases). All 16 quality gates apply.

---

## 🎯 SECTION 2 — IDENTITY & TARGET STATE

| Field | OLD | NEW |
|-------|-----|-----|
| Name | OpenForge | **OpenForge** |
| Tagline | "Terminal-first local AI agent" | **"Forge intelligent code, locally."** |
| CLI | forge, forge-chat, openforge, forge-gateway, forge-doctor | openforge, openforge-chat, openforge-agent, openforge-gateway, openforge-doctor |
| Py packages | forge, forge_cli | openforge, openforge_cli |
| Data dir | ~/.openforge/ | ~/.openforge/ |
| Install dir | ~/openforge/ | ~/.openforge/lib/ |
| Env prefix | FORGE_* | FORGE_* |
| Version target | 4.15.2 | **4.12.0 sequence continues as v4.15.x line is LIVE** — see Version Note below |

### ⚠️ Version Note (conflict resolution)
Prompt requests the sequence `...→ v4.11.1 → v4.12.0`. **Reality:** repo is already on **v4.15.2** with published releases v4.15.0/v4.15.1/v4.15.2. Tags/releases are immutable history. Going backward to v4.11.x would conflict with published tags and violate Section 17 (no orphan/duplicate). **Resolved path:** continue SemVer forward from the real current version. New sequence:
`v4.15.2 → Phase 1 = v4.16.0 (rename, MINOR) → Phase 2 = v4.17.0 (unified arch, MINOR) → Phase 3 = v4.18.0 (Web UI) → Phase 4 = v4.19.0 (TUI) → Phase 5 = v4.20.0 (Desktop, the "OpenForge Stable" capstone)`.
The spirit of the prompt (one MINOR per phase, feature-complete capstone) is preserved without rewriting published history.

---

## 🧱 SECTION 3 — CATEGORY → PHASE BREAKDOWN (the spine)

Work is decomposed **Category (K) → Phase (F) → Sub-phase (S)**. Each Phase is one
MINOR release. Within a Phase, Sub-phases are executed with the Hybrid Cycle
(Implement → Test → Evaluate → Pass/Fix), one at a time, never in parallel.

### KATEGORI A — BRAND & IDENTITY (rename surface)
### KATEGORI B — PYTHON CORE (packages, imports, env)
### KATEGORI C — FRONTEND (web rebrand + overhaul)
### KATEGORI D — UNIFIED ARCHITECTURE (~/.openforge/)
### KATEGORI E — TUI (Textual rewrite)
### KATEGORI F — DESKTOP (Tauri/Electron sidecar)
### KATEGORI G — MIGRATION & OPERABILITY (update/rollback/migrate/doctor)
### KATEGORI H — QUALITY & DOCS (tests, README SemVer, worklog)

---

### PHASE 1 — Rebrand + Agent System Prompt + Rename Surface → **v4.16.0**
*(Covers Kategori A + docs foundation; ensures the agent's own identity is correct FIRST per your instruction.)*

- **S1.0** Rewrite `SYSTEMPROMPT.md`: accurate capability counts (85 tools / 44 skills / 41 modules / 25 providers / C1–C9 categories), fix malformed lines 22-23, AND rebrand to OpenForge (name, tagline, FORGE_HOME paths, attribution). This is the explicit first task.
- **S1.1** Brand constants: `config.yaml` (name OpenForge, fix stale version), README.md (add SemVer policy section), GITHUB_ABOUT, LICENSE header, tagline propagation.
- **S1.2** Logo pipeline: make `public/icons/text_icon_open_forge.png` + `icon_shape_open_forge.png` background transparent (Pillow), wire into web headers/favicon.
- **S1.3** String-literal sweep for user-visible text: "OpenForge"→"OpenForge", "Forge"→"OpenForge" in docs + UI text (non-code).
- **Gate:** pytest ≥1097 pass; vitest 80/80; `config.yaml`/`pyproject` version consistent; build OK. Tag v4.16.0 + Release.

### PHASE 2 — Python Core Rename → **v4.17.0**
*(Covers Kategori B. Highest blast radius — isolated into its own phase.)*

- **S2.0** `git mv forge/ openforge/` and `git mv forge_cli/ openforge_cli/` (preserve history).
- **S2.1** Import rewrite across 208 `.py` (`from forge.` → `from openforge.`, `import forge_cli` → `import openforge_cli`), constants (`FORGE_HOME`→`FORGE_HOME`, all FORGE_* → FORGE_*), class `NexaAgent`→`OpenForgeAgent`, pyproject `[project.scripts]` entry points.
- **S2.2** Env var rename FORGE_*→FORGE_* with **compatibility shim** (read FORGE_* first, fall back to FORGE_*, emit deprecation warning).
- **S2.3** Optional `forge`→`openforge` re-export shim package (decision: see Section 0 mitigation).
- **S2.4** Update all 68 test files' imports + path/env assertions.
- **Gate:** pytest ≥1097 pass, zero `import forge` residue (negative grep), CLI `openforge --version` → 4.17.0. Tag + Release.

### PHASE 3 — Unified Architecture ~/.openforge/ → **v4.18.0**
*(Covers Kategori D + G-partial. New code, not rename.)*

- **S3.0** `openforge/path_resolver.py` (FORGE_HOME/FORGE_LIB/FORGE_WORKSPACE/… central resolution; `is_core_path`).
- **S3.1** `openforge/path_protection.py` (block writes into `lib/` from write_file/file_patch/run_terminal_command.
- **S3.2** `openforge/integrity.py` (LOCK file: SHA256 manifest of lib/, verify at startup/doctor, regenerate on update).
- **S3.3** Wire all hardcoded paths (state.py, memory_files, knowledge_cache, error_memory, trajectory_recorder, tools/_internal/paths, src/*) through the resolver.
- **S3.4** Installer rewrite (install.sh/install.ps1) → target `~/.openforge/lib/`, chmod 555 lib/, 700 secrets/, symlink `~/.local/bin/openforge`.
- **S3.5** `openforge update` / `rollback` / `migrate` subcommands (backup→.versions/→atomic swap→LOCK regen→doctor verify).
- **S3.6** Migration: ~/.openforge/→~/.openforge/, ~/openforge/→~/.openforge/lib/, ~/forge-workspace/→~/.openforge/workspace/ (backup before move, verify doctor green).
- **Gate:** pytest ≥1097 pass; fresh-install dry run; doctor green; migration reversible-tested. Tag + Release.

### PHASE 4 — Web UI Overhaul → **v4.19.0**
*(Covers Kategori C.)*

- **S4.0** Study OpenCode web (packages structure) — document takeaways before coding (per prompt rule #13).
- **S4.1** Migrate inline styles → Tailwind + Shadcn; 3-panel reactive layout (Sidebar | Chat | Tools/Skills panel).
- **S4.2** Skills (44) + Tools (85) status panels; Orchestrator-phase panel; provider status.
- **S4.3** Framer Motion transitions (idle/thinking/error); theme toggle light/dark/system; mobile responsive (390×844).
- **Gate:** eslint 0 errors, next build OK, vitest 80/80, visual smoke. Tag + Release.

### PHASE 5 — TUI Rewrite (Textual) → **v4.20.0**
*(Covers Kategori E.)*

- **S5.0** Rewrite `ui_tui/` from prompt_toolkit/rich → Textual (reactive, CSS, 3-panel, SSE to backend).
- **S5.1** Keyboard shortcuts, mouse, scroll; session sidebar + chat + tool log panel.
- **Gate:** pytest pass; TUI smoke (headless driver). Tag + Release.

### PHASE 6 — Desktop App (Tauri/Electron) → **v4.21.0 (OpenForge Stable)**
*(Covers Kategori F. Capstone.)*

- **S6.0** Choose Tauri (preferred for size/Rust sidecar) after confirming toolchain availability; wrap `openforge_web`.
- **S6.1** Manage `server.py` as sidecar; system tray; auto-update; app icon from transparent `icon_shape_open_forge.png`.
- **Gate:** desktop builds + launches, backend sidecar starts, UI renders; full quality gate Section 8. Tag v4.21.0 + Release.

---

## 🧪 SECTION 4 — QUALITY GATE (per Hybrid cycle, non-negotiable)

Per phase, before tagging:
- [ ] pytest ≥ current baseline (no negative delta; new behavior tested)
- [ ] vitest 80/80; eslint 0; next build OK (frontend phases)
- [ ] Version synced: pyproject.toml = package.json = openforge_web/package.json = config.yaml
- [ ] `openforge doctor` all-green (after Phase 3)
- [ ] No regression in 16-gate matrix; security scans 0 vulns (pip-audit / npm audit)
- [ ] Tag + GitHub Release (Section 17 trilogy, absolute-path gh.exe)

---

## ⛔ SECTION 5 — RISK REGISTER (top per phase)

| Phase | Top risk | Mitigation | Rollback |
|-------|----------|-----------|----------|
| 1 | Brand drift (mixed Forge/OpenForge strings) | literal sweep + grep assertion | revert commit |
| 2 | Import breakage across 208 files | mechanical rewrite + full pytest + compat shim | revert commit; shim keeps old import paths alive |
| 3 | Data loss in migration | mandatory pre-migration backup + dry-run + doctor verify | .backups restore; `.versions/` keep |
| 4 | UI regression / build break | incremental Tailwind migration, keep old components until swapped | keep prior components togglable |
| 5 | TUI perf on old laptop | profile Textual render; keep prompt_toolkit fallback behind env | feature-flag back to legacy TUI |
| 6 | Sidecar lifecycle (orphan python proc) | process_manager + PID file + health probe | kill sidecar; restart app |

---

## 🔄 SECTION 6 — ABORT / ESCALATION CRITERIA

HALT and ask you when: migration touches real user data irreversibly; a Phase fails 3 fix attempts;
a rename decision would drop external-API compatibility without the shim; or two fixes cause cascading new failures.

---

## 📋 SECTION 7 — DEFERRED (needs your explicit go before coding)

- Compatibility shim decision (Section 0 mitigation).
- Desktop stack final pick (Tauri vs Electron) — will confirm at Phase 6 based on toolchain availability.
- Repo rename on GitHub (neuralforgeio/openforge → neuralforgeio/openforge) — a remote/admin action I will NOT do autonomously.

---

*Plan complete. Awaiting approval to begin Phase 1 (SYSTEMPROMPT rewrite + rebrand surface).*
