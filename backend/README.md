# Nexa Agent — Python Backend

> **The advanced AI agent by Dearly Febriano Irwansyah**
> Version 1.0.0 · MIT License

A standalone FastAPI backend that mirrors the Hermes Agent architecture: an
iterative tool-calling agent loop, AsyncOpenAI streaming, SQLite+FTS5
persistence, and a WebSocket gateway for real-time chat.

## Features

- **Iterative agent loop** — the LLM can call tools, see results, and continue
  reasoning until it produces a final answer (up to 8 rounds per turn).
- **Native OpenAI function-calling** — tools are exposed via the standard
  `tools` parameter; the model calls them directly (no fragile text parsing).
- **Streaming** — tokens stream to the client in real time over WebSocket.
- **4 tools** — `read_file`, `write_file`, `run_terminal_command`, `generate_uuid`.
- **Sandboxed** — file & terminal operations are confined to `nexa-workspace/`.
- **SQLite persistence** — conversations and messages survive restarts.

## Project Structure

```
backend/
├── main.py              # FastAPI gateway (REST + WebSocket /ws/chat)
├── agent.py             # NexaAgent — core loop (run_streaming)
├── provider.py          # LLMProvider — AsyncOpenAI + streaming + tool dispatch
├── storage.py           # ConversationDB — aiosqlite (conversations + messages)
├── config.py            # Constants, env vars, NEXA_HOME resolution
├── requirements.txt     # Python dependencies
├── tools/
│   ├── __init__.py
│   ├── registry.py      # ToolRegistry + get_openai_schemas()
│   ├── file_tools.py    # read_file, write_file (sandboxed)
│   └── terminal_tool.py # run_terminal_command, generate_uuid
├── .env.example         # Environment variable template
└── README.md            # This file
```

## Quick Start

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

Or simply:

```bash
python main.py
```

The API will be available at `http://localhost:8000`.

### 4. Test the WebSocket endpoint

```python
import asyncio
import json
import websockets

async def test():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        await ws.send(json.dumps({"conversation_id": None, "message": "Generate a UUID"}))
        while True:
            response = json.loads(await ws.recv())
            print(response)
            if response["type"] in ("done", "error"):
                break

asyncio.run(test())
```

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/conversations` | List all conversations |
| `POST` | `/api/conversations` | Create a new conversation (`{"title": "..."}`) |
| `GET` | `/api/conversations/{id}` | Get a conversation's messages |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |

### WebSocket Endpoint

**`WS /ws/chat`**

**Send:**
```json
{"conversation_id": null, "message": "Hello, Nexa!"}
```

**Receive events:**
```json
{"type": "session", "conversation_id": "conv-...", "is_new": true}
{"type": "thinking"}
{"type": "token", "text": "Hello"}
{"type": "token", "text": "!"}
{"type": "tool_call", "name": "generate_uuid", "result": {"tool": "generate_uuid", "ok": true, "output": "...", "duration_ms": 1}}
{"type": "done", "answer": "Here's your UUID: ..."}
{"type": "error", "message": "..."}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_BASE_URL` | *(optional)* | Custom OpenAI-compatible endpoint (e.g. OpenRouter) |
| `NEXA_MODEL` | `gpt-4o` | The model to use |
| `NEXA_HOME` | `~/.nexa` | Runtime home directory (DB, memory) |
| `NEXA_WORKSPACE` | `./nexa-workspace` | File/terminal tool sandbox |

## Architecture (adapted from Hermes Agent)

```
User Input
    │
    ▼
NexaAgent.run_streaming()
    │
    ├─ Build system prompt (identity + tool catalog)
    ├─ Build transcript (system + history + user input)
    │
    ▼
LLMProvider.chat_stream()  ──── AsyncOpenAI (stream=True, tools=[...])
    │
    ├─ yield ("token", delta)          ──► WebSocket → frontend
    │
    ├─ if delta.tool_calls:
    │     ├─ ToolRegistry.execute(name, **args)
    │     ├─ yield ("tool_call", result) ──► WebSocket → frontend
    │     └─ feed result back to LLM ──► loop
    │
    └─ yield ("done")
    │
    ▼
ConversationDB.add_message()  ── SQLite persistence
```

## Connecting the Next.js Frontend

The Next.js frontend in `/src` can connect to this Python backend by
pointing WebSocket/REST calls to `http://localhost:8000`.

## License

Copyright (c) 2026 Dearly Febriano Irwansyah. Released under the MIT License.
