# OpenForge

> **Forge intelligent code, locally.** — by Dearly Febriano Irwansyah
> **Version 4.16.0** · MIT License · [SYSTEMPROMPT.md](./SYSTEMPROMPT.md)

OpenForge is a local-first, terminal-first AI agent with iterative tool-calling,
multi-provider support (25 providers + custom endpoints), a self-improvement
memory system, a large first-party skills library, a reactive TUI, and a full
Web UI (Next.js + React) with a sandbox panel and a work-process trace.

Everything lives under one unified home: **`~/.openforge/`**.

---

## Highlights (current)

- **43 built-in tools** (filesystem, terminal, git, planning, research,
  knowledge, multimodal, self-extension, MCP, delegation) — see
  `tools/registry.py :: create_default_registry()` for the ground truth.
- **44 skills across 6 categories** (`skills/`): Code Intelligence,
  Web & Research, Creative & Media, Communication, Data & Analytics,
  DevOps & Operations. Real implementations where possible (SQLite FTS5
  code_search, real DB queries, real stats); honest "not configured" stubs
  where an external service is missing.
- **41 intelligence modules** (`agent/`) — self-improvement, self-healing,
  autonomous web learning, knowledge cache, confidence scoring, intent
  classification, pattern recognition, adaptive persona, reasoning chain,
  context enrichment, memory consolidation, trajectory recording, and more.
- **25 providers + custom endpoints** — OpenAI, Anthropic, OpenRouter,
  Ollama, llama.cpp (local), LM Studio, vLLM, TokenRouter, Databricks, Groq,
  Mistral, Together, Fireworks, Cohere, Perplexity, DeepSeek, xAI, Gemini,
  Azure OpenAI, HuggingFace, Cerebras, SambaNova, and any OpenAI-compatible
  endpoint.
- **Unified `~/.openforge/` home** — code (`lib/`, read-only), user data
  (`memory/`, `secrets/`, `sessions/`, `logs/`, `cache/`), and the workspace
  (`workspace/`) in one place. See [Unified home](#unified-home-openforge).
- **Sandbox Panel (Web UI)** — 50/50 web preview + real PTY terminal.
- **Security hardened** — tool sandbox blocks `~/.openforge/` internals,
  AST-scan of user tools, opt-in auth/PTY, CSP headers.
- **Producer-grade local LLM support** — llama.cpp `--jinja` template is
  honored (single system message at index 0). Long local generations run with
  no client-side cancellation ("auto stop" fixed; see v4.15.1/4.15.2 notes).

---

## Versioning (Semantic Versioning 2.0.0)

OpenForge follows **Semantic Versioning 2.0.0** (see https://semver.org).
This policy is in effect starting with the OpenForge consolidation line
(v4.16.0 and later).

```
MAJOR.MINOR.PATCH
```

- **PATCH** (`x.y.Z+1`) — backward-compatible bug fixes, performance work,
  docs, tests, non-behavioral refactors.
- **MINOR** (`x.Y+1.0`) — backward-compatible new functionality: new tools,
  new skills, new endpoints (none removed), new config options, UX changes,
  and the OpenForge rename/unified-architecture (shipped with an
  auto-migration layer so existing user data keeps working).
- **MAJOR** (`X+1.0.0`) — backward-**incompatible** breaking change ONLY, and
  only on explicit user request (e.g. a removal of an old API, a manual data
  migration, an incompatible config format).

Examples: `4.15.228 → 4.16.0` (feature/refactor, MINOR), `4.16.0 → 5.0.0`
(breaking, MAJOR).

Every release updates the version in `pyproject.toml`, `package.json`,
`openforge_web/package.json`, and `config.yaml`, then tags git and creates a
GitHub Release. We never push a tag without a matching release.

---

## Quick Start

### One-Line Install (recommended)

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/neuralforgeio/openforge/main/scripts/install/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/neuralforgeio/openforge/main/scripts/install/install.ps1 | iex
```

The installer installs into `~/.openforge/lib/`, creates the venv, installs
deps, and runs `openforge setup`. Then, in a new terminal:

```bash
openforge provider list
openforge provider add tokenrouter
openforge provider use tokenrouter
openforge-chat
```

### Manual Install

```bash
git clone https://github.com/neuralforgeio/openforge.git
cd openforge
python -m venv .venv
# Linux/macOS:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -e ".[dev]"
openforge setup
openforge provider list
```

### Running the Agent

```bash
openforge-chat                      # interactive REPL
openforge-agent "Generate a UUID"   # single-turn
openforge --version                 # OpenForge v4.16.0
openforge doctor                    # self-health diagnostics
openforge gateway start             # backend on :8000
cd openforge_web && npm run dev     # web UI on :3000
```

---

## Unified home (`~/.openforge/`)

```
~/.openforge/
├── lib/            # OpenForge code (READ-ONLY, chmod 555) — renamed from nexa/
│   ├── openforge/  openforge_cli/  openforge_web/
│   ├── agent/      skills/         tools/   providers/
│   ├── ui_tui/     src/            config/  public/icons/
│   ├── VERSION     LOCK (sha256)   CHANGELOG.md
├── workspace/      # your project files (RW)
├── memory/         # MEMORY.md, USER.md, PROCEDURES.md
├── secrets/        # API keys (chmod 700/600)
├── sessions/  tools/  extensions/  logs/  cache/  .permissions/
├── .versions/      # previous lib snapshots (rollback)
├── .backups/       # auto backups
└── openforge.db    # SQLite + FTS5
```

Path resolution is centralized in `openforge/path_resolver.py` (planned in
Phase 3): no hardcoded paths, everything honors `FORGE_HOME` etc.

### CLI commands (high level)

| Command | Purpose |
|---|---|
| `openforge-chat` | Interactive chat REPL |
| `openforge-agent "<task>"` | Single-turn task |
| `openforge` | CLI with subcommands |
| `openforge setup` | Initialize `~/.openforge/` |
| `openforge doctor` | Self-health diagnostics (DB/disk/memory/LOCK) |
| `openforge update` / `rollback` / `migrate` | Release management (Phase 3) |
| `openforge-gateway` / `openforge-doctor` | Backend + health |

---

## Environment Variables (new `FORGE_*` prefix)

| Variable | Default | Description |
|---|---|---|
| `FORGE_PROVIDER` | `openai` | Provider name |
| `FORGE_MODEL` | provider-specific | Model identifier |
| `FORGE_BASE_URL` | provider-specific | Custom endpoint URL |
| `FORGE_API_TOKEN` | *(empty)* | Auth token (opt-in) |
| `FORGE_REQUIRE_AUTH` | `0` | Require API token in production |
| `FORGE_ENABLE_PTY` | `0` | Enable PTY terminal |
| `FORGE_ORCHESTRATOR` | `0` | Virtual multi-agent persona |
| `FORGE_QUICK_MODE` | `0` | No-tool instant answers |
| `FORGE_FAILOVER_ENABLED` | `0` | Provider failover |
| `FORGE_FAILOVER_CHAIN` | `openai,anthropic,ollama` | ordered failover list |
| `FORGE_HOME` | `~/.openforge` | Runtime home root |
| `FORGE_WORKSPACE` | `~/.openforge/workspace` | File/terminal sandbox |
| `FORGE_LLM_TIMEOUT` | `600` | LLM call timeout (seconds) |
| `FORGE_MAX_CONTEXT_MESSAGES` | `30` | Context window (messages) |
| `FORGE_MAX_TOOL_ITERATIONS` | `25` | Tool-call iteration cap |

> **Backward compatibility:** for one MINOR cycle, legacy `NEXA_*` env vars are
> honored with a deprecation warning (see `openforge/config.py`). Set the new
> `FORGE_*` names to silence it.

---

## Tools

The default registry currently exposes **43 tools**, grouped as:

- **Filesystem & patch**: `read_file`, `write_file`, `file_patch`, `file_info`,
  `list_directory`, `search_files`, `revert_file`
- **Execution & process**: `run_terminal_command`, `terminal_exec`,
  `code_execution`, `list_background_processes`, `kill_background_process`,
  `process_snapshot`, `list_ports`
- **VCS & planning**: `git_status`, `git_diff`, `git_log`, `git_checkpoint`,
  `todo_read`, `todo_write`, `task_plan`, `plan_and_delegate`,
  `project_scaffold`, `scratchpad_write`, `think`
- **Research & knowledge**: `web_search`, `web_fetch`, `deep_research`,
  `read_pdf`, `read_docx`, `read_xlsx`, `read_pptx`, `semantic_search`,
  `memory_search`, `session_search`
- **Creative / multimodal**: `image_generation`, `image_understanding`, `browser`
- **Self-extension & misc**: `delegate`, `create_tool`, `mcp_call`,
  `mcp_list_servers`, `generate_uuid`

Full schemas: `tools/registry.py`. Docs: `docs/tools.md`.

## Skills (44 handlers, 6 categories)

`skills/code_intelligence`, `skills/web_research`, `skills/creative_media`,
`skills/communication`, `skills/data_analytics`, `skills/devops_operations`.
Each skill is a provider-agnostic handler invoked via a shared LLM adapter.

---

## Self-Improvement System

OpenForge gets smarter the more you use it:

1. **Memory Curator** extracts preferences, facts, insights, skills per turn.
2. **File persistence** to `~/.openforge/memory/MEMORY.md` + `USER.md`
   (human-readable, editable).
3. **Learning Graph** tracks tool success/failure for smarter tool selection.
4. **Context injection** — memories are injected into the system prompt.

---

## Testing

```bash
python -m pytest tests/ -q          # Python (1,000+ tests)
cd openforge_web && npm run build   # Web UI build
cd openforge_web && npx vitest run  # Web UI tests
npx eslint .                        # Lint
```

Local LLM E2E (requires llama.cpp on `127.0.0.1:8080`):

```bash
$env:NEXA_E2E_LLAMACPP = "1"   # gate name kept for back-compat during migration
python -m pytest tests/test_llamacpp_real.py -v
```

> The no-timeout live tests intentionally avoid `asyncio.wait_for`; llama.cpp
> on a 9B Q4 model can legitimately take 5–10 minutes on slower hardware.

---

## History

Earlier Nexa-era versions (v1.x–v4.15.x) built the foundation: Python backend,
TUI, multi-provider, memory system, security hardening, cross-platform installer,
sandbox panel, planning tools, virtual multi-agent orchestrator, and 85+
tools/skills across 9 categories. See `AGENTS.md` and `worklog.md` for the full
evolution.

## License

Copyright (c) 2026 Dearly Febriano Irwansyah. Released under the MIT License.
