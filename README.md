# Nexa Agent

> **The advanced AI agent by Dearly Febriano Irwansyah**
> Version 1.0.0 · MIT License

A terminal-first AI agent with an iterative tool-calling loop, multi-provider
support (OpenAI, **Ollama**, **llama.cpp**, OpenRouter, vLLM, LM Studio), and
an interactive TUI built with prompt_toolkit + rich.

Inspired by the architecture of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(clean-room reimplementation — original code, adapted design patterns).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (choose your provider)
cp .env.example .env
# Edit .env: set NEXA_PROVIDER and NEXA_MODEL

# Run the interactive TUI
python cli.py

# Or run a single turn
python run_agent.py "Generate a UUID"

# Or with explicit provider
python cli.py --provider ollama --model llama3.2
python cli.py --provider openai --model gpt-4o
```

## Providers

Nexa Agent works with any OpenAI-compatible endpoint:

| Provider | `--provider` | Base URL | Default Model |
|----------|-------------|----------|---------------|
| OpenAI | `openai` | https://api.openai.com/v1 | gpt-4o |
| OpenRouter | `openrouter` | https://openrouter.ai/api/v1 | claude-3.5-sonnet |
| **Ollama** | `ollama` | http://localhost:11434/v1 | llama3.2 |
| **llama.cpp** | `llamacpp` | http://localhost:8080/v1 | local-model |
| LM Studio | `lmstudio` | http://localhost:1234/v1 | loaded-model |
| vLLM | `vllm` | http://localhost:8000/v1 | Llama-3.1-8B-Instruct |

### Using Ollama

```bash
# Install Ollama (https://ollama.com)
ollama pull llama3.2

# Run Nexa with Ollama
python cli.py --provider ollama --model llama3.2
```

### Using llama.cpp

```bash
# Start llama.cpp server
./llama-server -m model.gguf --port 8080

# Run Nexa with llama.cpp
python cli.py --provider llamacpp
```

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read a file from the workspace |
| `write_file` | Write/create a file in the workspace |
| `run_terminal_command` | Execute a shell command (15s timeout, output cap) |
| `generate_uuid` | Generate a UUID v4 |

All file/terminal operations are sandboxed to `nexa-workspace/`.

## TUI Commands

| Command | Action |
|---------|--------|
| `/help` | Show commands and providers |
| `/clear` | Clear the conversation |
| `/model <name>` | Change the model |
| `/provider <name>` | Change the provider |
| `/history` | Show conversation history |
| `/exit` | Exit (or Ctrl+D) |

## Project Structure

```
nexa-agent/
├── cli.py                  # Interactive TUI (prompt_toolkit + rich)
├── run_agent.py            # NexaAgent class + standalone runner
├── provider.py             # LLMProvider (AsyncOpenAI, streaming, tool dispatch)
├── storage.py              # ConversationDB (SQLite + aiosqlite)
├── config.py               # Environment & constants
├── nexa_bootstrap.py       # UTF-8 stdio setup (imported first)
├── nexa_constants.py       # Constants (single source of truth)
├── agent/                  # Core engine
│   ├── conversation_loop.py
│   └── prompt_builder.py
├── tools/                  # Tool implementations
│   ├── registry.py         # ToolRegistry + get_openai_schemas()
│   ├── file_tools.py       # read_file, write_file
│   └── terminal_tool.py    # run_terminal_command, generate_uuid
├── providers/              # Provider catalog & resolution
│   └── catalog.py          # Ollama, llama.cpp, OpenAI, OpenRouter, ...
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXA_PROVIDER` | `openai` | Provider name |
| `OPENAI_API_KEY` | *(required for OpenAI)* | API key |
| `NEXA_MODEL` | provider-specific | Model identifier |
| `NEXA_BASE_URL` | provider-specific | Custom endpoint URL |
| `NEXA_HOME` | `~/.nexa` | Runtime home directory |
| `NEXA_WORKSPACE` | `./nexa-workspace` | File/terminal sandbox |

## License

Copyright (c) 2026 Dearly Febriano Irwansyah. Released under the MIT License.
