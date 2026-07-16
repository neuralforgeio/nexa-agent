# Nexa Agent — Architecture

## Overview

Nexa Agent is a terminal-first local AI agent with an iterative tool-calling
loop, multi-provider LLM support, and a self-improvement memory system.

## Core Components

### 1. Entry Points (root level)

| File | Purpose |
|------|---------|
| `cli.py` | Interactive TUI with prompt_toolkit + rich |
| `run_agent.py` | NexaAgent class + standalone CLI runner |
| `server.py` | FastAPI SSE server for web UI integration |

### 2. nexa/ — Core Package

| Module | Responsibility |
|--------|---------------|
| `bootstrap.py` | UTF-8 stdio setup (imported first) |
| `constants.py` | NEXA_HOME, version, safeguards |
| `config.py` | Environment variable loading |
| `state.py` | SQLite + FTS5 persistence (conversations, messages, memories) |
| `provider.py` | LLMProvider — AsyncOpenAI with streaming + tool dispatch |

### 3. agent/ — Agent Engine

| Module | Responsibility |
|--------|---------------|
| `conversation_loop.py` | Core iterative tool-calling loop with hardening |
| `prompt_builder.py` | Dynamic system prompt assembly |
| `context_compressor.py` | Token budget management + LLM summarization |
| `memory_curator.py` | Self-improvement: extract insights from each turn |
| `memory_files.py` | MEMORY.md + USER.md file management |
| `learning_graph.py` | Tool success rate tracking |
| `error_classifier.py` | API error categorization (TRANSIENT/AUTH/FATAL) |
| `message_sanitizer.py` | JSON repair + message cleanup |
| `iteration_budget.py` | Tool-call iteration limits (max 8 per turn) |
| `self_health.py` | Diagnostics for /doctor command |
| `session_search.py` | FTS5 full-text search across sessions |

### 4. tools/ — Tool Implementations

| Module | Tools |
|--------|-------|
| `registry.py` | ToolRegistry + create_default_registry() |
| `file_tools.py` | read_file, write_file |
| `terminal_tool.py` | run_terminal_command, generate_uuid |
| `delegate_tool.py` | delegate (sub-agent spawning) |

### 5. providers/ — Provider Catalog

| Module | Responsibility |
|--------|---------------|
| `catalog.py` | ProviderConfig for 6 providers + resolve_provider() |

## Agent Loop Flow

```
User Input
    │
    ▼
NexaAgent.run_streaming()
    │
    ├─ Build system prompt (identity + tools + memory digest)
    ├─ Build transcript (system + history + user input)
    │
    ▼
conversation_loop.run_conversation()
    │
    ├─ Sanitize messages (strip surrogates, repair JSON)
    ├─ Compress context if over token budget
    │
    ▼
LLMProvider.chat_stream()  ←── AsyncOpenAI (stream=True, tools=[...])
    │
    ├─ yield token deltas          ──► TUI/UI renders streaming text
    │
    ├─ if tool_calls:
    │     ├─ ToolRegistry.execute(name, **args)
    │     ├─ Record outcome in learning graph
    │     ├─ yield tool_result      ──► TUI/UI shows tool card
    │     └─ feed result back to LLM ──► loop
    │
    └─ Final answer
    │
    ▼
Memory Curator: extract insights → DB + MEMORY.md/USER.md
    │
    ▼
ConversationDB: persist user message + tool results + answer
```

## Data Flow

### Local Storage (~/.nexa/)

```
~/.nexa/
├── nexa.db              ← SQLite (conversations, messages, memories, learning_graph)
│   ├── conversations    ← id, title, parent_session_id, timestamps
│   ├── messages          ← id, conversation_id, role, content, tool_name, token_count
│   ├── memories          ← id, kind, content, source, confidence, times_used
│   ├── learning_graph    ← node_type, node_value, success, failure, last_seen
│   ├── messages_fts      ← FTS5 virtual table (full-text search on messages)
│   └── memories_fts      ← FTS5 virtual table (full-text search on memories)
├── memory/
│   ├── MEMORY.md         ← Agent notes (insights, skills) — human-readable
│   └── USER.md           ← User profile (preferences, facts) — human-readable
├── sessions/             ← Session data
└── logs/                 ← Application logs
```

### Self-Improvement Loop

1. User sends a message
2. Agent processes and responds (with optional tool calls)
3. **Memory Curator** analyzes the turn:
   - Pattern matching detects preferences, facts, insights, skills
   - FTS5 deduplication prevents duplicate memories
   - New memories stored in SQLite + appended to MEMORY.md/USER.md
4. **Learning Graph** records tool success/failure
5. **System Prompt** for next turn includes accumulated memories
6. Agent gets progressively smarter across sessions

## Web UI Integration

The Next.js frontend (local, not pushed to GitHub) connects to the Python
agent via the `server.py` FastAPI server:

```
Browser → Next.js (port 3000) → /api/* proxy → Python server (port 8000)
```

The proxy is configured in `next.config.ts`:
```js
rewrites: () => [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]
```

## Testing

Tests use pytest with pytest-asyncio:

```bash
uv run pytest tests/ -v
```

| Test File | Coverage |
|-----------|----------|
| `test_tool_registry.py` | Registry, schemas, UUID, file I/O, terminal, timeout |
| `test_error_classifier.py` | Error categorization, retry guidance |
| `test_session_search.py` | FTS5 search, snippets, match counts |
| `test_memory_system.py` | File I/O, sections, sync, curator integration |
| `test_delegate_tool.py` | Registration, schema, prompt builder, pending calls |
