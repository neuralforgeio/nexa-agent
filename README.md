# Nexa Agent

> **The Ultimate Local AI Agent Enterprise — by Dearly Febriano Irwansyah**
> **Version 4.6.4** · MIT License · [SYSTEMPROMPT.md](./SYSTEMPROMPT.md)

A terminal-first local AI agent with iterative tool-calling, multi-provider
support (24 providers + custom endpoints), a self-improvement memory system,
an interactive TUI (Textual-style multi-pane, built with prompt_toolkit + rich),
and a full Web UI (Next.js + React).

**v4.5.0 highlights**

- **40 AI Skills system** (`skills/`): 6 categories × 40 = 240 files
  (40 handlers + 40 manifest.yaml + 40 __init__.py × 6) covering
  Code Intelligence, Web & Research, Creative & Media, Communication,
  Data & Analytics, DevOps & Operations. Real implementations where possible
  (SQLite code_search index, real DB queries, real stats), honest stubs where
  not (no external service = clearly marked "not configured").
- **TUI redesign**: 4-panel live terminal UI; `/skills` browser with search;
  `/tools` lists all 40 skills; `/sessions` manager; `/memory` editor;
  `/doctor` + `/export` + `/persona`/`/config`/`/history` — all 18 slash commands.
- **Server API**: `GET /api/skills` + `POST /api/skills/{name}/execute` for
  the web UI or scripts to call skills directly.
- **Tests**: **980 passed** (957 pre-skills with 24 skill programs + 33 TUI checks).

**v4.4.0 highlights** (Batch 8 — Skills System)

- 40 skills across 6 categories — mest all specs: manifest + handler +
  handler.py + tests (input validation, happy path, executor, prompt
  fidelity, failure propagation).
- **llama.cpp**: Real-LLM E2E tests against Ornith (local 9B model) via
  `NEXA_E2E_LLAMACPP=1`; tested 10 skills end-to-end.
- **Frontend**: SettingsPanel now has a Skills tab w/ category filter + search
  + execute button + result viewer.
- **code_search**: Real SQLite FTS5 index (not a stub).
- **database_querying**: Real SQLite row execution (list of dicts).
- **data_analysis**: Real CSV stats; spreadsheet uses openpyxl if installed.

**v4.1.0 highlights** (for context)

- **Sandbox Panel** — right-hand sidebar with a vertically-split
  **Web Preview** (top half) and **real PTY Terminal** (bottom half).
  Autodetects Next/Vite/Astro dev servers; for plain HTML/CSS/JS, falls back
  to serving the workspace via `/api/sandbox/preview`.
- **Working Process dropdown** — every reasoning step + tool call is shown
  in a collapsible trace that auto-collapses once the answer lands (with a
  one-line summary).
- **30+ built-in tools** — the planning toolkit (task_plan, todo_write,
  scratchpad, think, project_scaffold, git_checkpoint, list_ports,
  process_snapshot, memory_search, session_search, web_fetch, create_tool,
  plan_and_delegate, …) on top of the 13 core tools.
- **`create_tool`** — the agent can literally extend *itself* by drafting a
  new tool into `~/.nexa/tools/` (loaded automatically next turn).
- **llama.cpp auto-cancel fixed** — SSE keepalive pings + capability
  negotiation mean long prompt-processing no longer looks like a dropped
  client (no more `srv stop: cancel task`).
- **Double-process fix** — `nexa/process_manager.py` acquires a PID-
  file singleton for `server.py`, so `python server.py` twice never
  double-binds port 8000.
- **33-agent intelligence mesh** — reasoning chains, memory curator, error
  classifier, self-healer, prompt expander, intent classifier, persona
  adapter, trajectory recorder, semantic memory… and the v4.0 planner
  (now fully wired into the system prompt as of v4.1.0).

## Features

- **24 Providers + Custom Endpoints** — Anthropic Claude, Google Gemini, Mistral, Groq,
  Together, Fireworks, DeepSeek, xAI, Cohere, Perplexity, LocalAI, textgen, Jan,
  KoboldCpp, LiteLLM, Helicone, plus the original OpenAI/OpenRouter/Ollama/llama.cpp/
  LM Studio/vLLM/TokenRouter/Databricks, and any OpenAI-compatible custom endpoint.
- **Local AI Architecture** — All user data, memory, and state stored in `~/.nexa/`
- **Interactive TUI** — Streaming responses, slash commands, tool visualization,
  multi-pane layout (status bar + chat + tool log + input)
- **Web UI** — Next.js + React with collapsible sidebar (`Ctrl+B`), sandbox
  (`Ctrl+J`), streaming chat, tool cards, SettingsPanel, TerminalPanel
- **33 Tools** — 13 core (read_file, write_file, run_terminal_command,
  delegate, code_execution, web_search, file_patch, …) + 20 planning tools
  (added v4.0, hardened v4.1)
- **30+ Intelligence Modules** — Self-improvement, self-healing, autonomous
  web learning, knowledge cache, confidence scoring, intent classification,
  pattern recognition, error memory, adaptive persona, reasoning chain,
  fact validator, context enricher, memory consolidator, query reformulator
- **File-Based Memory** — `~/.nexa/memory/MEMORY.md` + `USER.md` (human-editable)
  + `~/.nexa/PROCEDURES.md` playbook injected into the system prompt
- **SQLite + FTS5** — Full-text search across all past conversations
- **Provider Failover** — Automatic switch to the next healthy provider on failure
- **Security Hardened** — Terminal blocks `~/.nexa/` access (API keys safe),
  project-scoped sandbox, HITL approval for code execution
- **Self-Health Diagnostics** — `/doctor` command checks DB, disk, memory, learning graph
- **Learning Graph** — Tracks tool success rates for data-driven decisions
- **User-Writable Tool Directory** — `~/.nexa/tools/*.py` files are auto-loaded
  into the registry (self-extension pattern inspired by skill systems)

## Quick Start

### One-Line Install (recommended)

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install/install.sh| bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install/install.ps1 | iex
```

The installer auto-detects/installs Python 3.11+, uv, clones the repo, creates
a virtual environment, installs dependencies, and runs `nexa setup`. After it
finishes, open a **new terminal** and run:

```bash
nexa provider list          # see all 24 providers
nexa provider add tokenrouter   # interactive — prompts for API key + model
nexa provider use tokenrouter   # activate
nexa-chat                       # start chatting!
```

### Manual Install (alternative)

```bash
# Prerequisites: Python 3.11+ and git
git clone https://github.com/neuralforgeio/nexa-agent.git
cd nexa-agent

# Create venv + install
python -m venv .venv
# Linux/macOS:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -e ".[dev]"

# Initialize
nexa setup
nexa provider list
```

### Configure a Provider

**TokenRouter** (recommended — OpenAI-compatible routing gateway):

```bash
nexa provider add tokenrouter
# ? API key (input hidden): tr_your_key_here
# ? Model ID [auto:balance]:
nexa provider use tokenrouter
nexa provider test tokenrouter
```

**OpenAI** (direct):

```bash
export OPENAI_API_KEY="sk-..."        # Linux/macOS
$env:OPENAI_API_KEY = "sk-..."        # Windows PowerShell
nexa provider use openai
```

**Ollama** (local, free):

```bash
ollama pull llama3.2          # install Ollama first from ollama.com
nexa provider add ollama
nexa provider use ollama
```

**Custom endpoint** (any OpenAI-compatible):

```bash
nexa provider add my-llm \
  --base-url "https://my-llm.example.com/v1" \
  --api-key "sk-mykey" \
  --model "my-model-v1"
nexa provider use my-llm
```

See [docs/providers.md](./docs/providers.md) for the full provider guide.

### Running the Agent

```bash
# Interactive chat REPL
nexa-chat
# Or with explicit provider:
nexa-chat --provider ollama --model llama3.2

# Single-turn (non-interactive)
nexa-agent "Generate a UUID"

# Multi-pane TUI (status bar + chat + tool log + input)
python -m ui_tui.app

# CLI subcommands
nexa setup            # initialize ~/.nexa/
nexa doctor           # self-health diagnostics
nexa gateway start    # start backend (port 8000)
nexa gateway status   # check if running
nexa provider list    # list all 24 providers
nexa provider test openai  # health check

# Web UI server (backend on port 8000, frontend on port 3000)
nexa gateway start                       # backend
cd nexa_web && npm install && npm run dev  # frontend (Next.js)
# Open http://localhost:3000 in your browser
```

See [docs/MANUAL_TESTING_GUIDE.md](./docs/MANUAL_TESTING_GUIDE.md) for the
full manual testing walkthrough (CLI, TUI, Web UI, terminal security, E2E).

## Providers

Nexa Agent works with any OpenAI-compatible endpoint:

| Provider | `--provider` | Base URL | Default Model | API Key |
|----------|-------------|----------|---------------|---------|
| OpenAI | `openai` | https://api.openai.com/v1 | gpt-4o | Required |
| OpenRouter | `openrouter` | https://openrouter.ai/api/v1 | claude-3.5-sonnet | Required |
| **Ollama** | `ollama` | http://localhost:11434/v1 | llama3.2 | Any string |
| **llama.cpp** | `llamacpp` | http://localhost:8080/v1 | local-model | Any string |
| LM Studio | `lmstudio` | http://localhost:1234/v1 | loaded-model | Any string |
| vLLM | `vllm` | http://localhost:8000/v1 | Llama-3.1-8B-Instruct | Any string |

### Using Ollama (Local AI)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2

# Run Nexa with Ollama
python cli.py --provider ollama --model llama3.2
```

### Using llama.cpp

```bash
# Start llama.cpp server
./llama-server -m model.gguf --port 8080

# Run Nexa
python cli.py --provider llamacpp
```

## Tools

### Core (13 tools)

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from the workspace |
| `write_file` | Write/create a file in the workspace |
| `run_terminal_command` | Execute a shell command (15s timeout, output cap) |
| `generate_uuid` | Generate a UUID v4 |
| `delegate` | Spawn a sub-agent for a focused subtask |
| `list_background_processes` | List agent-spawned background processes |
| `kill_background_process` | Terminate a background process |
| `web_search` | DuckDuckGo search (no API key) |
| `code_execution` | Run a Python snippet in a sandboxed subprocess |
| `file_patch` | Apply a unified diff with atomic write + backup |
| `revert_file` | Roll back to a previous version |
| `deep_research` | Multi-source research with citations |
| `terminal_exec` | Terminal command with session persistence |

### Planning Toolkit (20 tools — added v4.0, hardened v4.1)

**Planning & reasoning**

| Tool | Description |
|------|-------------|
| `task_plan` | Decompose a goal into a dependency-aware plan (template-matched) |
| `todo_write` | Create/update a named TODO list in `.nexa/todos/` |
| `todo_read` | Read a TODO list (or list them all) |
| `scratchpad_write` | Append/replace the workspace scratchpad |
| `think` | Loop-back reasoning tool — narrate an internal step |

**Filesystem**

| Tool | Description |
|------|-------------|
| `list_directory` | Tree-style listing with sizes + glob excludes |
| `search_files` | Recursive regex search over workspace text files |
| `file_info` | Size, mtime, line count, MIME, sha256 |
| `project_scaffold` | Starter code for next / vite-react / express / fastapi / static / python-cli |

**Git (workspace-local)**

| Tool | Description |
|------|-------------|
| `git_status` | Branch + porcelain status + last commit |
| `git_diff` | Unified diff (working tree or staged) |
| `git_log` | Recent commits (`hash · subject · age`) |
| `git_checkpoint` | Stage-and-commit a snapshot for rollback |

**Process & system**

| Tool | Description |
|------|-------------|
| `list_ports` | Which dev-server ports are listening (+ PID on Windows) |
| `process_snapshot` | Regex-filtered snapshot of user processes |

**Knowledge**

| Tool | Description |
|------|-------------|
| `memory_search` | FTS5 search over long-term memories |
| `session_search` | FTS5 search over past conversation messages |
| `web_fetch` | Fetch a URL and extract readable text (32 KB cap) |

**Self-extension**

| Tool | Description |
|------|-------------|
| `create_tool` | Write a new tool into `~/.nexa/tools/` (auto-loaded next turn) |
| `plan_and_delegate` | Plan a goal AND emit a ready delegate-prompt per step |

All file/terminal operations are sandboxed to `nexa-workspace/` (or the
`NEXA_WORKSPACE` env var you've set). Read-only tools may read project
files but never mutate anything outside the workspace.

## Sandbox Panel (Web UI)

The web UI at `http://localhost:3000` ships with a new right-hand sidebar
called the **Sandbox**:

```
┌──────────── Chat ────────────┬── Sandbox (toggle with Ctrl+J) ──┐
│                              │                                  │
│  messages & streaming        │   ┌─ Web Preview ──────────────┐ │
│  responses                   │   │  - recursive file tree     │ │
│                              │   │  - iframe preview of your  │ │
│  [Working Process ▾]         │   │    HTML/CSS/JS             │ │
│   ├── step 1: thinking       │   │  - dev-server autodetect   │ │
│   ├── step 2: tool call      │   └─────────────────────────────┘ │
│   └── step 3: result         │   ════════  draggable divider ════ │
│                              │   ┌─ Terminal (real PTY) ───────┐ │
│  Ask Nexa anything…          │   │  $ npm install               │ │
│                              │   │  $ npm run dev               │ │
│                              │   └─────────────────────────────┘ │
│                              │                                  │
└──────────────────────────────┴──────────────────────────────────┘
```

- **Three pane modes** — `both` (preview over terminal 50/50), `preview-only`,
  `terminal-only`. Drag the divider to resize; double-click to focus.
- **Autodetect** — Nexa watches common dev ports (3000, 5173, 4321, 4200,
  8080) and points the preview at the first one listening.
- **Workspace fallback** — if no dev server is running, the preview can
  render any file directly from `NEXA_WORKSPACE` (with syntax highlighting
  for code, image rendering for assets, a simple shell for `.js` files).
- **Real PTY terminal** — via xterm.js + WebSocket; shell starts inside
  the workspace so `cd myproject` just works.

## User-extensible tools (`~/.nexa/tools/`)

Ask Nexa to make a tool and it will write a new Python module into
`~/.nexa/tools/` using `create_tool` — then reload the *next* turn to
use it immediately. Everything in that folder is user-editable (the
runtime is read-only for you, but `~/.nexa/` is entirely yours).

---

## TUI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands and providers |
| `/tools` | Show all available tools with schemas |
| `/search <query>` | Search past conversations (FTS5 full-text) |
| `/memory [show\|sync]` | View/sync memory files (MEMORY.md + USER.md) |
| `/memories` | Show accumulated agent memories (learning store) |
| `/model <name>` | Change the current model |
| `/provider <name>` | Change the LLM provider |
| `/history` | Show conversation history |
| `/doctor` | Run self-health diagnostics |
| `/clear` | Clear the current conversation |
| `/exit` | Exit (or Ctrl+D) |

## Architecture

```
nexa-agent/
├── cli.py                  # Interactive TUI (prompt_toolkit + rich)
├── run_agent.py            # NexaAgent class + standalone runner
├── server.py               # FastAPI SSE server for web UI
├── nexa/                   # Core package
│   ├── bootstrap.py        # UTF-8 stdio setup
│   ├── constants.py        # NEXA_HOME, version, safeguards
│   ├── config.py           # Environment variable loading
│   ├── state.py            # SQLite + FTS5 persistence
│   └── provider.py         # LLMProvider (AsyncOpenAI, streaming, tools)
├── agent/                  # Agent engine
│   ├── conversation_loop.py    # Core iterative tool-calling loop
│   ├── prompt_builder.py       # Dynamic system prompt assembly
│   ├── context_compressor.py   # Token budget management + summarization
│   ├── memory_curator.py       # Self-improvement (extracts insights)
│   ├── memory_files.py         # MEMORY.md + USER.md file management
│   ├── learning_graph.py       # Tool success rate tracking
│   ├── error_classifier.py     # API error categorization + retry
│   ├── message_sanitizer.py    # JSON repair + message cleanup
│   ├── iteration_budget.py     # Tool-call iteration limits
│   ├── self_health.py          # Diagnostics (/doctor)
│   └── session_search.py       # FTS5 full-text session search
├── tools/                  # Tool implementations
│   ├── registry.py         # ToolRegistry + OpenAI schemas
│   ├── file_tools.py       # read_file, write_file
│   ├── terminal_tool.py    # run_terminal_command, generate_uuid
│   └── delegate_tool.py    # Sub-agent delegation
├── providers/              # Provider catalog
│   └── catalog.py          # OpenAI, Ollama, llama.cpp, vLLM, etc.
├── tests/                  # pytest test suite (50+ tests)
├── docs/                   # Documentation
│   ├── tools.md            # Tool reference
│   ├── architecture.md     # System design overview
│   └── providers.md        # Provider setup guides
├── requirements.txt
├── pyproject.toml
├── .env.example
└── NEXA_MASTER_PLAN.md
```

## ~/.nexa/ Directory Structure

```
~/.nexa/
├── nexa.db                 # SQLite database (conversations, messages, memories)
├── memory/
│   ├── MEMORY.md           # Agent notes (insights, skills)
│   └── USER.md             # User profile (preferences, facts)
├── sessions/               # Session data
└── logs/                   # Application logs
```

## Self-Improvement System

Nexa Agent gets smarter the more you use it:

1. **Memory Curator** — After each turn, analyzes the conversation and extracts:
   - **Preferences** (e.g., "user prefers Python")
   - **Facts** (e.g., "user's name is Dearly")
   - **Insights** (e.g., "the key to fixing X is Y")
   - **Skills** (e.g., "successfully used read_file tool")
2. **File Persistence** — Memories are written to `MEMORY.md` and `USER.md` (human-readable, editable)
3. **Learning Graph** — Tracks tool success/failure rates for smarter tool selection
4. **Context Injection** — Memories are injected into the system prompt for cross-session recall

## Testing

```bash
# Run all tests
uv run pytest tests/ -v
# Or:
python -m pytest tests/ -v
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXA_PROVIDER` | `openai` | Provider name |
| `OPENAI_API_KEY` | *(required for OpenAI)* | API key |
| `NEXA_MODEL` | provider-specific | Model identifier |
| `NEXA_BASE_URL` | provider-specific | Custom endpoint URL |
| `NEXA_HOME` | `~/.nexa` | Runtime home directory |
| `NEXA_WORKSPACE` | `./nexa-workspace` | File/terminal tool sandbox |

## License

Copyright (c) 2026 Dearly Febriano Irwansyah. Released under the MIT License.
