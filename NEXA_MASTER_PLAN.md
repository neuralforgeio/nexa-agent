# NEXA MASTER PLAN
**Nexa Agent — Terminal-First Local AI Agent**
Version 1.7.0 · Author: Dearly Febriano Irwansyah · MIT License

> This document is the source of truth for Nexa Agent's architecture,
> development roadmap, and maintenance schedule. It is updated by the
> autonomous cron system after every development cycle.

---

## 1. Project Overview

Nexa Agent is a **local-first AI agent** built entirely in Python. It runs
as a terminal application (TUI) with an iterative tool-calling loop,
multi-provider LLM support, and a self-improvement memory system. All user
data is stored locally at `~/.nexa/`.

### Core Principles
- **100% Original** — All code is written from scratch by Dearly Febriano Irwansyah.
- **Local-First** — No cloud dependencies for data storage. User data stays on-device.
- **Terminal-Native** — The primary interface is a TUI, not a web app.
- **Self-Improving** — The agent learns from each conversation and gets smarter over time.
- **Multi-Provider** — Works with OpenAI, Ollama, llama.cpp, vLLM, LM Studio, OpenRouter.

---

## 2. Architecture

```
nexa-agent/
├── cli.py                  # Interactive TUI (prompt_toolkit + rich)
├── run_agent.py            # NexaAgent class + standalone runner
├── server.py               # FastAPI SSE server (port 8000)
├── nexa/                   # Core package
│   ├── bootstrap.py        # UTF-8 stdio setup
│   ├── constants.py        # NEXA_HOME, version, safeguards
│   ├── config.py           # Environment variable loading
│   ├── state.py            # SQLite + FTS5 persistence
│   └── provider.py         # LLMProvider (AsyncOpenAI, streaming, tools)
├── agent/                  # Agent engine (12 modules)
│   ├── conversation_loop.py    # Iterative tool-calling loop
│   ├── prompt_builder.py       # Dynamic 8-section system prompt
│   ├── context_compressor.py   # Token budget + LLM summarization
│   ├── memory_curator.py       # Self-improvement (insight extraction)
│   ├── memory_files.py         # MEMORY.md + USER.md management
│   ├── learning_graph.py       # Tool success rate tracking
│   ├── error_classifier.py     # API error categorization + retry
│   ├── message_sanitizer.py    # JSON repair + message cleanup
│   ├── iteration_budget.py     # Tool-call iteration limits
│   ├── self_health.py          # Diagnostics (/doctor)
│   └── session_search.py       # FTS5 full-text session search
├── tools/                  # Tool implementations (5 tools)
│   ├── registry.py         # ToolRegistry + OpenAI schemas
│   ├── file_tools.py       # read_file, write_file
│   ├── terminal_tool.py    # run_terminal_command, generate_uuid
│   └── delegate_tool.py    # Sub-agent delegation
├── providers/              # Provider catalog (6 providers)
│   └── catalog.py          # OpenAI, Ollama, llama.cpp, vLLM, etc.
├── tests/                  # pytest test suite (87 tests)
├── docs/                   # Documentation
│   ├── tools.md            # Tool reference
│   ├── architecture.md     # System design
│   └── providers.md        # Provider setup guides
└── .plans/                 # Internal planning
    └── qa_log.md           # QA cycle log
```

---

## 3. Autonomous Development System

Nexa Agent is developed by an autonomous cron system with 3 cycles:

| Cron | Schedule | Role | Priority |
|------|----------|------|----------|
| **Cron 1** | Every 60 min | R&D: Architecture analysis, weakness identification, superior design | 5 |
| **Cron 2** | Every 30 min | Dev: Strict TDD implementation, documentation, staging commit | 10 |
| **Cron 3** | Every 10 min | QA: Destructive testing, fuzzing, auto-heal, release | 15 |

### Cron Workflow
1. **Cron 1** researches and designs → writes spec to worklog.md
2. **Cron 2** implements via TDD → stages commit (does NOT push)
3. **Cron 3** tests destructively → if stable, pushes + releases; if buggy, auto-heals + pushes patch

### Resilience Protocol
- Progress state saved in worklog.md after every cycle
- If a cron crashes, the next cycle resumes from the last checkpoint
- No task is repeated from scratch if partially completed

---

## 4. Development Roadmap

### Completed
| # | Feature | Version | Tests |
|---|---------|---------|-------|
| 1 | Context Engine (compression + token budget) | v1.0.0 | ✓ |
| 2 | FTS5 Session Search + /search command | v1.1.0 | 8 tests |
| 3 | Memory System (MEMORY.md + USER.md + /memory) | v1.2.0 | 15 tests |
| 4 | Subagent Delegation (delegate tool) | v1.3.0 | 13 tests |
| 5 | Dynamic Prompt Builder (8 sections) | v1.4.0 | 27 tests |
| - | Bug fix: empty terminal command | v1.7.0 | 2 tests |

### In Progress
| # | Feature | Status |
|---|---------|--------|
| 6 | Terminal Backends (PTY, output truncation, background processes) | NEXT |

### Upcoming
| # | Feature |
|---|---------|
| 7 | More Tools: web_search, code_execution, file_patch |
| 8 | TUI Enhancement: /sessions, /export, /config |
| 9 | Provider Failover: health check + automatic failover |
| 10 | Trajectory Recording |
| 11 | CLI Entry Point: `pip install nexa-agent` → `nexa` command |
| 12 | Config File: ~/.nexa/config.yaml |

### Future Enterprise Features
| # | Feature |
|---|---------|
| 13 | TUI Dashboard: multi-pane (chat, token usage, tool logs) |
| 14 | Subagent Orchestration: RPC via asyncio without deadlock |
| 15 | Context Compression Engine: async non-blocking summarization |
| 16 | MCP Integration: external MCP server support |

---

## 5. Current State

- **Version**: v1.7.0
- **Tests**: 87 passing
- **Tools**: 5 (read_file, write_file, run_terminal_command, generate_uuid, delegate)
- **Agent modules**: 12
- **Providers**: 6 (openai, openrouter, ollama, llamacpp, lmstudio, vllm)
- **TUI commands**: /help /tools /search /memory /memories /doctor /model /provider /history /clear /exit
- **Storage**: ~/.nexa/ (nexa.db, memory/MEMORY.md, memory/USER.md)
- **GitHub**: github.com/neuralforgeio/nexa-agent

---

## 6. Maintenance Schedule

### QA Log
QA results are tracked in `.plans/qa_log.md` after every Cron 3 cycle.

### Versioning Policy
- **MAJOR (vX.0.0)**: Architecture overhaul (e.g., new package structure)
- **MINOR (v1.X.0)**: New feature (e.g., new tool, new TUI command)
- **PATCH (v1.0.X)**: Bug fix, test addition, documentation update
- Patch numbers can go very high (v1.4.300, v1.4.587) for frequent auto-heal fixes

### Token Safety
- GitHub token stored in `~/.git-credentials` (never in tracked files)
- Verified every cycle: `git grep 'ghp_'` must return nothing

---

## 7. Quality Standards

- **Test Coverage**: All new features MUST have tests before push
- **Docstrings**: Every Python file MUST have module/class/method docstrings with Args/Returns/Raises
- **Documentation**: README.md and docs/ MUST be updated every development cycle
- **Originality**: No references to external AI agent projects in any tracked file
- **Edge Case Testing**: Fuzzing + chaos engineering every QA cycle

---

*This document is automatically maintained by the Nexa Autonomous Principal Engineer cron system.*
*Last updated: v1.7.0 cycle*
