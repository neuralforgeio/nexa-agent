# OpenForge — Architecture Analysis

> Internal design document for OpenForge's core subsystems.

## 1. Agent Loop
The conversation loop orchestrates: system prompt assembly → LLM call →
tool dispatch → result feedback → iteration until final answer.

**Forge**: `agent/conversation_loop.py` — `run_conversation()` async generator
with iteration budget, error classification, message sanitization, context
compression, memory curation, and learning graph integration.

## 2. Tool System
Central registry with OpenAI function-calling schema generation and
safe dispatch (never raises — returns ToolResult with ok=False).

**Forge**: `tools/registry.py` — `ToolRegistry` with `register()`,
`execute()`, `get_openai_schemas()`, `describe()`. 4 default tools:
read_file, write_file, run_terminal_command, generate_uuid.

## 3. Provider System
AsyncOpenAI client with streaming (stream=True), tool-call dispatch,
and retry with exponential backoff for transient errors.

**Forge**: `forge/provider.py` — `LLMProvider` with `chat_stream()` async
generator yielding token deltas and tool results. Multi-provider support
via `providers/catalog.py` (OpenAI, Ollama, llama.cpp, vLLM, etc.).

## 4. State & Storage
SQLite with FTS5 full-text search for conversation persistence.

**Forge**: `forge/state.py` — `ConversationDB` with conversations, messages,
memories, and learning_graph tables. FTS5 virtual tables on messages and
memories for semantic search.

## 5. Memory & Config
Home directory at ~/.openforge/ with memory store for cross-session learning.

**Forge**: `agent/memory_curator.py` — extracts insights, preferences, facts,
and skills from each turn. `forge/constants.py` — FORGE_HOME, FORGE_VERSION,
FORGE_WORKSPACE, env var resolution.
