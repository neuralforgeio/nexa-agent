# Nexa Agent

> **The advanced local AI agent by Dearly Febriano Irwansyah**
> Version 1.3.0 · MIT License

A terminal-first local AI agent with iterative tool-calling, multi-provider
support (OpenAI, Ollama, llama.cpp, vLLM, LM Studio, OpenRouter), a
self-improvement memory system, and an interactive TUI built with
prompt_toolkit + rich.

## Features

- **Local AI Architecture** — All user data, memory, and state stored in `~/.nexa/`
- **Interactive TUI** — Streaming responses, slash commands, tool visualization
- **Multi-Provider** — OpenAI, Ollama, llama.cpp, LM Studio, vLLM, OpenRouter
- **5 Tools** — read_file, write_file, run_terminal_command, generate_uuid, delegate (sub-agent)
- **Self-Improvement** — Memory curator extracts insights from each conversation
- **File-Based Memory** — `~/.nexa/memory/MEMORY.md` and `USER.md` (human-readable, editable)
- **SQLite + FTS5** — Full-text search across all past conversations
- **Context Compression** — Automatically summarizes old messages to fit token limits
- **Error Classification** — Smart retry with exponential backoff for transient errors
- **Self-Health Diagnostics** — `/doctor` command checks DB, disk, memory, learning graph
- **Learning Graph** — Tracks tool success rates for data-driven decisions

## Quick Start

### Prerequisites

- Python 3.11+ (recommended via [uv](https://docs.astral.sh/uv/))
- [uv](https://docs.astral.sh/uv/) for Python package management
- [bun](https://bun.sh/) for optional frontend operations

### Installation

```bash
# Clone the repository
git clone https://github.com/neuralforgeio/nexa-agent.git
cd nexa-agent

# Install Python dependencies
uv pip install -r requirements.txt
# Or with pip:
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit .env to set your provider and API key:
# NEXA_PROVIDER=ollama          # or openai, openrouter, llamacpp, lmstudio, vllm
# NEXA_MODEL=llama3.2           # or gpt-4o, claude-3.5-sonnet, etc.
# OPENAI_API_KEY=sk-your-key    # required for OpenAI/OpenRouter
```

### Running the Agent

```bash
# Interactive TUI
python cli.py
# Or with explicit provider:
python cli.py --provider ollama --model llama3.2
python cli.py --provider openai --model gpt-4o

# Single-turn (non-interactive)
python run_agent.py "Generate a UUID"

# Web UI server (for frontend integration)
python server.py
# Server runs on http://localhost:8000
```

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

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from the workspace |
| `write_file` | Write/create a file in the workspace |
| `run_terminal_command` | Execute a shell command (15s timeout, output cap) |
| `generate_uuid` | Generate a UUID v4 |
| `delegate` | Spawn a sub-agent for a focused subtask |

All file/terminal operations are sandboxed to `nexa-workspace/`.

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
