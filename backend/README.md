# Nexa Agent — Python Backend

The Python backend is a standalone FastAPI service that mirrors the Hermes Agent
architecture: agent loop with iterative tool calling, provider resolution,
SQLite+FTS5 storage, and WebSocket streaming.

## Quick Start

```bash
cd backend
pip install -r requirements.txt

# Set your API key
export NEXA_API_KEY="sk-..."
# Optional: custom OpenAI-compatible endpoint
export NEXA_BASE_URL="https://openrouter.ai/api/v1"
# Optional: model override
export NEXA_MODEL="gpt-4o"

# Run
uvicorn nexa.main:app --reload --port 8000
```

## Architecture

```
backend/nexa/
├── __init__.py
├── constants.py          # NEXA_HOME, NEXA_VERSION, env vars
├── agent.py              # NexaAgent — core loop (run_conversation + run_streaming)
├── provider.py           # LLMProvider — AsyncOpenAI with retry/backoff + streaming
├── state.py              # SQLite + FTS5 (conversations, messages, full-text search)
├── memory.py             # ~/.nexa/memory/ manager (MEMORY.md, USER.md)
├── main.py               # FastAPI gateway (REST + WebSocket)
└── tools/
    ├── __init__.py
    ├── base.py           # NexaTool abstract class + ToolResult
    ├── registry.py       # ToolRegistry + get_openai_schemas()
    ├── builtin_tools.py  # echo, calculate, get_time, generate_uuid
    ├── file_tools.py     # read_file, write_file, list_dir (sandboxed)
    └── terminal_tool.py  # run_terminal_command (timeout + output cap)
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/conversations` | List all conversations |
| POST | `/api/conversations` | Create a new conversation |
| GET | `/api/conversations/:id` | Get conversation messages |
| DELETE | `/api/conversations/:id` | Delete a conversation |
| POST | `/api/chat` | Non-streaming chat |
| GET | `/api/models` | List available models |
| GET | `/api/health` | Health check |
| WS | `/ws/chat` | WebSocket streaming chat |

## WebSocket Protocol

Send:
```json
{"message": "Generate a UUID", "conversation_id": null, "history": []}
```

Receive events:
```json
{"type": "thinking"}
{"type": "tool_call", "tool": "generate_uuid", "arguments": {}}
{"type": "tool_result", "result": {"tool": "generate_uuid", "ok": true, "output": "..."}}
{"type": "done", "answer": "Here's your UUID: ...", "iterations": 2}
```

## Environment Variables

| Var | Default | Description |
|---|---|---|
| `NEXA_API_KEY` | — | OpenAI API key (or `OPENAI_API_KEY`) |
| `NEXA_BASE_URL` | — | Custom OpenAI-compatible endpoint |
| `NEXA_MODEL` | `gpt-4o` | Model to use |
| `NEXA_HOME` | `~/.nexa` | Runtime home directory |
| `NEXA_WORKSPACE` | `./nexa-workspace` | File/terminal tool sandbox |

## Connecting the Next.js Frontend

The frontend in `/src` can connect to this Python backend by pointing API
requests to `http://localhost:8000`. Update `src/lib/api.ts` (or fetch calls)
to use the Python backend URL instead of the built-in Next.js API routes.

Copyright (c) 2026 Dearly Febriano Irwansyah · MIT License
