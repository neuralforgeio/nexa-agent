# Nexa Architecture Analysis
**Adaptasi pola desain Hermes Agent (NousResearch/hermes-agent, MIT) ke Nexa Agent**

> Catatan: repo Hermes tidak dapat di-fetch langsung dari sandbox ini.
> Analisis berdasarkan dokumentasi arsitektur publik AI agent dan pola standar
> yang direplikasikan secara clean-room di Nexa Agent.

---

## 1.1 Arsitektur Inti

### Hermes: `run_agent.py` + `agent/prompt_builder.py` + `agent/context_compressor.py`
- **Agent loop**: input user → rakit system prompt → call LLM → parse tool_calls
  → eksekusi tool → feed result kembali → ulang sampai LLM beri jawaban final.
- **Prompt builder dinamis**: system prompt dirakit dari identitas + tool
  catalog + memory digest + context terkompresi.
- **Context compressor**: jika transcript melebihi token limit, ringkas
  pesan lama menjadi summary agar context window tidak overflow.

### Padanan Nexa
- `src/lib/nexa/agent.ts` → `NexaAgent.runConversation()` — loop iteratif
  dengan `NEXA_MAX_TOOL_ITERATIONS` (8) sebagai safeguard.
- `buildSystemPrompt()` — merakit identitas Nexa + tool catalog
  (`registry.describe()`) + memory digest (`renderMemoryDigest()`).
- **Context compression**: belum diimplementasi (rekomendasi fase depan);
  saat ini pakai `NEXA_MAX_CONTEXT_MESSAGES` (30) windowing — pesan lama
  di-truncate, bukan di-summarize.

---

## 1.2 Tool System

### Hermes: `model_tools.py` + `tools/registry.py` + `tools/file_tools.py` + `tools/terminal_tool.py`
- **Registry terpusat**: tool didaftarkan, schema dikumpul, dispatch terjadwal.
- **Schema generation**: format OpenAI function calling (`{type, function:{name, description, parameters}}`).
- **Tool implementations**: file ops (read/write/list), terminal exec, dll.

### Padanan Nexa
- `src/lib/nexa/tools/registry.ts` → `ToolRegistry` dengan `register()`,
  `execute()` (timing-captured, never-throws), `schemas()`,
  `describe()` (human-readable), **`getOpenAiSchemas()`** (OpenAI format).
- `src/lib/nexa/tools/base.ts` → `NexaTool` abstract class dengan
  `name`, `description`, `parameters`, `category`, `execute()`.
- 18 tools terdaftar:
  - Builtins: `echo`, `get_time`, `calculate`, `generate_uuid`, `base64`
  - Memory: `save_memory`, `recall_memory`, `list_memory`, `forget_memory`
  - Notes: `save_note`, `list_notes`, `clear_notes`
  - Web: `web_search`, `web_fetch`
  - Filesystem: `read_file`, `write_file`, `list_dir`, `run_terminal_command`

---

## 1.3 Provider System

### Hermes: `agent/runtime_provider.py`
- Resolve provider (OpenAI direct, OpenRouter, custom OpenAI-compatible endpoint).
- Load credentials dari env/config per provider.
- Support streaming via `AsyncOpenAI` dengan `stream=True`.

### Padanan Nexa
- `src/lib/nexa/provider.ts` → `LLMProvider` wrapping `z-ai-web-dev-sdk`.
- Singleton client (`getClient()`) untuk reuse koneksi.
- `chatCompletion()` dengan retry+backoff untuk 429/5xx (4 attempts: 1s→2s→4s→8s).
- `buildSystemPrompt()` static — stamp identitas Nexa.
- **Streaming**: TBD di fase D — cek apakah SDK support `stream:true`,
  fallback pseudo-streaming jika tidak.

---

## 1.4 State & Storage

### Hermes: `hermes_state.py` — SQLite + FTS5
- Tabel: conversations, messages, metadata.
- FTS5 untuk full-text search across conversations.
- Async via aiosqlite.

### Padanan Nexa
- `prisma/schema.prisma` → 4 model:
  - `NexaSession` (id, title, createdAt, updatedAt) + relations messages/notes
  - `NexaMessage` (id, sessionId, role, content, toolName, toolCallId, createdAt)
  - `NexaMemory` (id, kind, content, createdAt) — long-term, cross-session
  - `NexaNote` (id, sessionId, content, pinned, createdAt) — per-session scratchpad
- `src/lib/db.ts` → Prisma client singleton (log: query di dev).
- **FTS5**: belum diimplementasi; search saat ini pakai `LIKE` substring
  (cukup untuk skala saat ini, rekomendasi fase depan: tambah FTS5 virtual table).

---

## 1.5 Memory & Config

### Hermes: `agent/memory_manager.py` + `hermes_constants.py` + `hermes_cli/config.py`
- Direktori home: `~/.hermes/` dengan subdirs (sessions, skills, memory, logs).
- Files: `MEMORY.md` (agent notes), `USER.md` (user profile).
- Constants: `HERMES_HOME`, `HERMES_PROFILE`, `HERMES_BIN`.
- Env vars: `HERMES_API_KEY`, `HERMES_BASE_URL`, `HERMES_MODEL`.

### Padanan Nexa
- `src/lib/nexa/constants.ts`:
  - `NEXA_HOME = "~/.nexa"` (logical namespace, DB-backed di web build)
  - `NEXA_PROFILE = "default"`
  - `NEXA_DIRS` (sessions, skills, memory, logs) — logical paths
  - `NEXA_MEMORY_FILES` (MEMORY.md, USER.md) — logical names
  - `NEXA_WORKSPACE` — filesystem sandbox untuk file/terminal tools
  - `NEXA_VERSION = "1.0.0"`, `NEXA_AUTHOR`, `NEXA_DEFAULT_MODEL`
- `src/lib/nexa/memory.ts` → `saveMemory`, `recallMemory`, `listMemory`,
  `deleteMemory`, `renderMemoryDigest` (injected ke system prompt).
- Env vars konseptual: `NEXA_API_KEY`, `NEXA_BASE_URL`, `NEXA_MODEL`
  (di web build, SDK handle credentials internal; tidak perlu env eksplisit).

---

## Ringkasan Gap (untuk fase berikutnya)

| Fitur Hermes | Status Nexa | Prioritas |
|---|---|---|
| Agent loop iteratif | ✅ Ada | — |
| Tool registry + OpenAI schema | ✅ Ada (18 tools) | — |
| Provider resolution + retry | ✅ Ada | — |
| SQLite persistence | ✅ Ada (Prisma) | — |
| Memory orchestration | ✅ Ada | — |
| Streaming response | ❌ Belum | **Fase D (sekarang)** |
| Context compression | ❌ Belum | Fase depan |
| FTS5 full-text search | ❌ Belum (pakai LIKE) | Fase depan |
| `~/.nexa/` filesystem | ❌ N/A (web) | Konseptual saja |
