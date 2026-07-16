# NEXA MASTER PLAN
**Nexa Agent — Terminal-First AI Agent (Hermes-style clean-room reimplementation)**
Version 1.0.0 · Author: Dearly Febriano Irwansyah · MIT License

> This document is the source of truth for Nexa Agent's architecture and
> phased roadmap. It adapts the design of NousResearch/hermes-agent (MIT)
> into an original codebase, structured root-level (no `backend/` wrapper).

---

## 1. Vision

Nexa Agent is a **terminal-first AI agent** — a Python CLI/TUI that runs an
iterative tool-calling loop against any OpenAI-compatible LLM (OpenAI,
OpenRouter, **Ollama**, **llama.cpp**, LM Studio, vLLM, etc.). It mirrors
Hermes Agent's core architecture: root-level Python modules, an `agent/`
engine package, a `tools/` package, and a prompt_toolkit+rich TUI.

**Key principle**: the GitHub repo contains **only the agent** (Python,
root-level). The web frontend stays local in the dev panel and is NOT
pushed to GitHub — exactly like Hermes which ships a CLI, not a webapp.

---

## 2. Root-Level Structure (mirrors Hermes)

```
nexa-agent/
├── pyproject.toml              # build config, deps, entry points
├── requirements.txt            # pip install -r
├── nexa_bootstrap.py           # UTF-8 stdio setup (imported first)
├── nexa_constants.py            # NEXA_HOME, NEXA_VERSION, stable IDs
├── nexa_state.py               # SQLite + FTS5 session store
├── nexa_logging.py             # cross-platform logging
├── nexa_time.py                # timezone helpers
├── run_agent.py                # NexaAgent class + standalone runner
├── cli.py                      # prompt_toolkit + rich TUI REPL
├── provider.py                 # LLMProvider (AsyncOpenAI, multi-endpoint)
├── toolsets.py                 # named tool groups
├── utils.py                    # shared helpers
│
├── agent/                      # core engine
│   ├── __init__.py
│   ├── conversation_loop.py    # the run_conversation method
│   ├── prompt_builder.py       # dynamic system prompt assembly
│   ├── context_compressor.py   # context window management
│   └── tool_executor.py        # tool dispatch + guardrails
│
├── tools/                      # tool implementations
│   ├── __init__.py
│   ├── registry.py             # ToolRegistry + get_openai_schemas()
│   ├── file_tools.py           # read_file, write_file, list_dir
│   ├── terminal_tool.py        # run_terminal_command, generate_uuid
│   └── builtin_tools.py        # calculate, get_time, echo
│
├── providers/                  # provider catalog & resolution
│   ├── __init__.py
│   ├── base.py                 # abstract provider
│   ├── openai_provider.py      # OpenAI direct
│   ├── ollama_provider.py      # Ollama (localhost:11434)
│   ├── llamacpp_provider.py    # llama.cpp server
│   └── catalog.py              # provider registry
│
├── .env.example                # environment template
├── .gitignore
├── LICENSE                     # MIT
├── README.md                   # documentation
└── NEXA_MASTER_PLAN.md         # this file
```

---

## 3. Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | >=3.11, <3.14 |
| Package manager | pip / uv | latest |
| LLM client | openai (AsyncOpenAI) | >=1.50 |
| CLI/TUI | **prompt_toolkit** + **rich** | 3.0.x / 14.x |
| Storage | aiosqlite (SQLite + FTS5) | >=0.20 |
| Config | python-dotenv, pyyaml | latest |
| Resilience | tenacity (retry/backoff) | >=9.0 |
| Markdown | rich.markdown | built-in |

**No FastAPI in the core repo** — the agent is a CLI/TUI, not a server.
(An optional `gateway/` package can be added later for messaging bridges.)

---

## 4. Multi-Provider Support

Nexa Agent supports any OpenAI-compatible endpoint via `NEXA_BASE_URL`:

| Provider | NEXA_BASE_URL | NEXA_MODEL example |
|----------|--------------|-------------------|
| OpenAI | *(default)* | gpt-4o |
| OpenRouter | https://openrouter.ai/api/v1 | anthropic/claude-3.5-sonnet |
| **Ollama** | http://localhost:11434/v1 | llama3.2, qwen2.5, mistral |
| **llama.cpp** | http://localhost:8080/v1 | local-model |
| LM Studio | http://localhost:1234/v1 | loaded-model |
| vLLM | http://localhost:8000/v1 | meta-llama/Llama-3.1-8B-Instruct |

A `providers/catalog.py` maps friendly names to base URLs so users can run:
```
nexa --provider ollama --model llama3.2
nexa --provider openai --model gpt-4o
```

---

## 5. Phased Roadmap

### Phase 1 — Root-Level Restructure (current)
- [x] Move all Python from `backend/` to repo root
- [ ] Remove frontend (`src/`, `prisma/`, etc.) from git tracking
- [ ] Remove panel artifacts (`.zscripts/`, `mini-services/`, `download/`)
- [ ] Commit clean repo

### Phase 2 — Multi-Provider Support
- [ ] `providers/` package with Ollama, llama.cpp, OpenRouter adapters
- [ ] `--provider` CLI flag + `NEXA_PROVIDER` env var
- [ ] Provider auto-detection (health check on base_url)
- [ ] Model listing for local providers (`ollama list`)

### Phase 3 — TUI (prompt_toolkit + rich)
- [ ] Interactive REPL with multiline editing
- [ ] Streaming token rendering with rich markdown
- [ ] Slash commands (/help, /clear, /model, /provider, /history)
- [ ] Tool-call visualization (collapsible cards)
- [ ] Conversation history (FileHistory at ~/.nexa/history)
- [ ] Interrupt support (Ctrl+C)

### Phase 4 — Agent Loop Hardening
- [ ] Context compression when transcript exceeds token limit
- [ ] Iteration budget (max tool calls per turn)
- [ ] Error classification + adaptive retry
- [ ] Message sanitization (strip images, repair JSON)

### Phase 5 — Tools Expansion
- [ ] web_search, web_fetch (httpx)
- [ ] Memory tools (save/recall across sessions)
- [ ] Code execution sandbox
- [ ] Delegate tool (subagents)

### Phase 6 — Distribution
- [ ] `pip install nexa-agent` from PyPI
- [ ] `nexa` entry point globally available
- [ ] Docker image
- [ ] Homebrew formula

---

## 6. Risk Identification

| Risk | Mitigation |
|------|-----------|
| Ollama not running | Graceful error + `nexa setup ollama` guide |
| prompt_toolkit not installed | Fallback to input()/print() basic mode |
| Token overflow | Context compressor summarizes old messages |
| Tool infinite loop | Iteration budget (max 8 rounds) |
| Path traversal | Workspace sandbox + resolve validation |
| Rate limits | tenacity retry with exponential backoff |

---

## 7. Definition of Done (Phase 1-3)

- [ ] Repo root has flat Python structure (no `backend/` folder)
- [ ] No frontend files tracked in git
- [ ] `nexa` CLI launches TUI
- [ ] TUI streams tokens from at least 2 providers (OpenAI + Ollama)
- [ ] Tool calls (file/terminal/uuid) work from TUI
- [ ] Tested in real terminal
- [ ] Pushed to GitHub, clean of panel artifacts
