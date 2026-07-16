# NEXA MASTER PLAN
**Nexa Agent v1.0.0 — Architecture & Execution Plan**
Author: Dearly Febriano Irwansyah · MIT License

> Dokumen ini adalah sumber kebenaran arsitektur Nexa Agent. Disusun sebelum
> satu baris kode pun ditulis ulang, sebagai mandated oleh TUGAS 0.

---

## 1. Visi & Arsitektur Umum

Nexa Agent adalah AI agent canggih yang arsitekturnya **diadaptasi** dari
NousResearch/hermes-agent (MIT). Adaptasi berarti: kita menyerap pola desain
inti — agent loop iteratif, tool registry terpusat, provider resolution
pluggable, state persisten dengan FTS, dan memory orchestration — lalu
menulisnya ulang orisinal dengan TypeScript/Next.js, bukan menyalin kode
Python.

### Adaptasi environment (penting)
Spec asli meminta FastAPI (Python) + WebSocket. Environment ini adalah
**Next.js 16 monorepo** (TypeScript). Membangun Python backend terpisah tidak
viable di sini. Adaptasi yang dipilih:

| Konsep Hermes (Python) | Implementasi Nexa (Next.js/TS) | Alasan |
|---|---|---|
| FastAPI app | Next.js App Router API routes | Satu proses, satu bahasa, hot-reload |
| `asyncio` agent loop | `async`/`await` di route handler | Native di Node.js |
| `aiosqlite` + FTS5 | Prisma + SQLite | Type-safe, migrations, sudah terpasang |
| WebSocket `/ws/chat` | **SSE** `/api/chat/stream` | One-way stream cukup untuk chat; lebih simpel, auto-reconnect native browser, tidak butuh mini-service terpisah |
| `AsyncOpenAI` SDK | `z-ai-web-dev-sdk` | SDK bawaan environment, backend-only |
| `~/.nexa/` files | Prisma tables + logical `NEXA_HOME` namespace | Web app tidak punya akses filesystem user; DB sebagai pengganti |

**Outcome fungsional identik**: streaming token-by-token, tool calling iteratif,
persistensi percakapan, full-text search.

### Prinsip desain
1. **Clean-room**: kode orisinal, pola diadaptasi, tidak menyalin.
2. **Modular**: setiap tool/provider/service adalah modul independen terdaftar di registry.
3. **Toleran terhadap error**: tool gagal → `ok:false`, bukan crash. LLM transient error → retry+backoff.
4. **Sandboxed**: file/terminal tools terbatas pada `nexa-workspace/`.
5. **Streaming-first**: respons LLM dialirkan token-by-token ke UI.

---

## 2. Struktur Folder & File

Struktur sudah ada dan baik; ini dokumen resminya:

```
nexa-agent/
├── prisma/
│   └── schema.prisma              # NexaSession, NexaMessage, NexaMemory, NexaNote
├── public/
│   └── nexa-agent.png             # Logo (favicon, avatar, OG)
├── src/
│   ├── app/
│   │   ├── layout.tsx             # Inter + JetBrains Mono, dark default, logo meta
│   │   ├── page.tsx               # Orchestrator: sidebar + chat + panels + shortcuts
│   │   ├── globals.css            # Design system (dark #0F0F0F, accent #4A9EFF)
│   │   └── api/
│   │       ├── chat/route.ts              # POST: non-streaming agent turn
│   │       ├── chat/stream/route.ts       # POST: SSE streaming agent turn ★NEW
│   │       ├── sessions/route.ts          # GET/POST list/create
│   │       ├── sessions/[id]/route.ts     # GET/PATCH/DELETE
│   │       ├── memory/route.ts            # GET/POST/DELETE
│   │       ├── notes/route.ts             # GET/POST (per-session scratchpad)
│   │       ├── notes/[id]/route.ts        # PATCH/DELETE
│   │       └── export/[id]/route.ts       # GET markdown export
│   ├── components/
│   │   ├── nexa/
│   │   │   ├── sidebar.tsx        # Sessions, date grouping, search, rename/export/delete
│   │   │   ├── composer.tsx       # Pill-shaped, auto-grow, suggestion chips
│   │   │   ├── transcript.tsx     # Message stream + empty state + thinking
│   │   │   ├── message-block.tsx  # User bubble / assistant full-width / tool output
│   │   │   ├── markdown.tsx       # react-markdown + code blocks + copy
│   │   │   ├── tool-step.tsx      # Collapsible tool call/result cards
│   │   │   ├── status-bar.tsx     # Model, session, status
│   │   │   ├── memory-panel.tsx   # Long-term memory CRUD
│   │   │   ├── notes-panel.tsx    # Per-session scratchpad
│   │   │   └── command-palette.tsx# ⌘K fuzzy search
│   │   └── theme-provider.tsx     # next-themes wrapper
│   └── lib/
│       ├── db.ts                  # Prisma client singleton
│       └── nexa/
│           ├── constants.ts       # NEXA_HOME, NEXA_VERSION, NEXA_WORKSPACE
│           ├── types.ts           # Shared interfaces
│           ├── agent.ts           # NexaAgent core loop (iterative tool calling)
│           ├── provider.ts        # LLMProvider (z-ai-web-dev-sdk + retry/backoff)
│           ├── memory.ts          # Long-term memory CRUD
│           ├── notes.ts           # Per-session scratchpad CRUD
│           └── tools/
│               ├── base.ts        # NexaTool abstract class
│               ├── registry.ts    # ToolRegistry + getOpenAiSchemas()
│               ├── builtins.ts    # echo, get_time, calculate, uuid, base64
│               ├── memory-tools.ts# save/recall/list/forget memory
│               ├── notes-tools.ts # save/list/clear notes
│               ├── web-tools.ts   # web_search, web_fetch
│               └── fs-tools.ts    # read_file, write_file, list_dir, run_terminal_command
├── nexa-workspace/                # Sandboxed filesystem for file/terminal tools (gitignored)
├── NEXA_MASTER_PLAN.md            # Dokumen ini
├── .plans/nexa-architecture-analysis.md  # Analisis Hermes
└── worklog.md                     # Development handover log
```

---

## 3. Tech Stack

| Lapisan | Teknologi | Versi |
|---|---|---|
| Framework | Next.js (App Router) | 16 |
| Bahasa | TypeScript | 5 |
| Styling | Tailwind CSS + CSS variables | 4 |
| UI components | shadcn/ui (New York) + Lucide | latest |
| Markdown | react-markdown + remark-gfm | latest |
| Database | Prisma + SQLite | 6 |
| AI SDK | z-ai-web-dev-sdk (backend-only) | 0.0.18 |
| Theming | next-themes | 0.4 |
| State | React hooks + fetch (no global store needed) | — |
| Streaming | Server-Sent Events (native Response stream) | — |

**Tidak dipakai** (dan alasannya): FastAPI (bukan env ini), WebSocket/socket.io
(SSE cukup untuk one-way chat stream, lebih simpel), Zustand (state lokal
cukup), aiosqlite (Prisma sudah async).

---

## 4. Alur Eksekusi

### Fase A — Planning (TUGAS 0)
- ✅ Dokumen ini dibuat.

### Fase B — Analisis Hermes (TUGAS 1)
- `.plans/nexa-architecture-analysis.md`: dekomposisi 5 subsistem Hermes
  (agent loop, tool system, provider, state, memory) dan padanannya di Nexa.
- Catatan: repo Hermes tidak bisa di-fetch langsung dari sandbox; analisis
  berdasarkan dokumentasi arsitektur publik dan pola standar AI agent.

### Fase C — Perbaikan UI (TUGAS 2)
- Scan & hapus SEMUA `emerald`/`green`/`teal` di komponen sekunder
  (boot-sequence, command-palette, memory-panel, notes-panel, sidebar).
- Ganti dengan `text-primary`/`bg-accent`/`border-primary` (blue #4A9EFF).
- Verifikasi: `grep -rn "emerald\|green-" src/` → 0 hasil.

### Fase D — Streaming Backend (TUGAS 3)
- Tambah `NexaAgent.runStreaming()` — generator yang `yield` event:
  `thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`.
- Cek apakah z-ai SDK support `stream: true`; jika ya, stream token asli;
  jika tidak, chunk respons final menjadi token simulated.
- Provider: tambah `chatCompletionStream()` returning async iterable.

### Fase E — Streaming API + Frontend (TUGAS 4)
- `POST /api/chat/stream` — SSE: kirim `Content-Type: text/event-stream`,
  flush setiap event.
- Frontend: `useStreamingChat` hook — `fetch` + `ReadableStream` reader,
  parse SSE events, append token ke assistant message real-time dengan
  blinking caret, tampilkan tool cards saat event masuk.

### Fase F — Testing (TUGAS 5)
- Skenario: generate_uuid, write_file, read_file, refresh+persist, warna.
- Verifikasi via agent-browser.

---

## 5. Identifikasi Risiko & Solusi

| Risiko | Dampak | Solusi |
|---|---|---|
| SDK tidak support `stream:true` | Tidak ada token stream asli | Fallback: chunk respons final jadi pseudo-token (10ms interval) — UX tetap live |
| Tool call JSON malformed dari LLM | Tool tidak tereksekusi, markup bocor | `repairJson()` (sudah ada) + 5-level tolerant parser + markup stripping |
| 429 rate limit saat multi-round tool call | Turn gagal | Retry exponential backoff 1s→2s→4s→8s (sudah ada di provider) |
| SSE connection dropped | Stream terputus | Browser auto-reconnect untuk GET; untuk POST fetch, frontend deteksi abort → tampilkan "retry" |
| Terminal command hang | Agent stuck | `timeout: 15_000` + `SIGKILL` (sudah ada) |
| Path traversal via file tools | Akses file sistem host | `resolveInWorkspace()` reject `..` dan absolute path (sudah ada) |
| Prisma connection exhaustion | API 500 | Singleton client (sudah ada) |
| Hydration mismatch (theme) | UI flicker | `suppressHydrationWarning` + `mounted` guard (sudah ada) |

---

## 6. Definition of Done

- [x] Master plan dibuat (dokumen ini)
- [ ] Analisis Hermes dibuat
- [ ] 0 warna emerald/green di `src/`
- [ ] Streaming API merespons `text/event-stream`
- [ ] Frontend menampilkan token real-time dengan caret
- [ ] Tool cards muncul inline saat streaming
- [ ] Refresh page → history tetap
- [ ] 5 skenario test lulus via agent-browser
- [ ] Lint 0 error
