# OpenForge — Manual Testing Guide

> **Version**: v4.2.1+ | **Creator**: Dearly Febriano Irwansyah | **License**: MIT

Panduan lengkap untuk menguji OpenForge secara manual: instalasi, provider config, CLI, TUI, Web UI, terminal security, dan skenario end-to-end.

Implicitly the v4 line adds: persona-driven orchestrator (FORGE_ORCHESTRATOR=1),
expanded provider catalog (24), hardened AST gate for user tools, atomic
write_file, FTS5 message triggers, and the v4.2.1 path-hygiene fix.

---

## Quick Start (Ornith llama.cpp)

Jika Anda punya llama.cpp berjalan di port 8080:

```bash
# 1. Add Ornith provider (one-time setup)
forge provider add ornith --base-url http://127.0.0.1:8080/v1 --api-key dummy --model "Ornith-1.0-9b-Q4_K_M.gguf"

# 2. Activate it
forge provider use ornith

# 3. Start chatting (TUI)
forge-chat
```

That's it! Provider tersimpan di `~/.openforge/secrets/providers.json` dan bertahan antar restart.

---

## Web UI Test (Auto-start)

Backend + Frontend:

```bash
# Terminal 1: Backend (port 8000)
forge gateway start

# Terminal 2: Frontend (port 3000)
cd forge_web && npm run dev
```

Buka http://localhost:3000 di browser. Klik ⚙ (Settings) di sidebar → provider "ornith" → Test → Use.

---

## CLI Test (interactive REPL)

```bash
forge-chat
```

Then inside the REPL:

```
forge > /help                         # show all commands
forge > /provider list               # show all 8 providers
forge > /provider use ornith         # switch to Ornith
forge > /model Ornith-1.0-9b      # set model
forge > Hello! Give me a one-word answer.   # chat
forge > /exit                        # quit
```

Atau single-turn:

```bash
openforge "What is the capital of France?"
```

---

## TUI Test (multi-pane)

```bash
python -m ui_tui.app
```

Layout:

```
┌─ OpenForge v4.1.0 │ model: Ornith-1.0-9b │ tokens: ~0 │ server: UP │ 14:32 ─┐
├──────────────────────────────────────┬─────────────────────────────────────┤
│ Chat                                                       │ Tool Log:        │
│                                                            │                  │
│ You: Hello!                                                │ ✓ read_file      │
│                                                            │   (45ms)         │
│ Forge: Hi! I'm Forge, your local assistant.              │                  │
│ You: What can you do?                                      │                  │
│                                                            │                  │
├──────────────────────────────────────┴─────────────────────────────────────┤
│ forge > _                                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

TUI slash commands:

```
/ help                    # show commands
/provider list            # list providers
/provider use ornith    # switch
/model <name>          # set model
/doctor                # health check
/memories               # show memories
/exit                   # quit
```

---

## Security Test (terminal)

```bash
# Izinkan akses ke file workspace
forge > read file forge-workspace/notes.txt
✓ read_file (12ms): "Hello from Forge!"

# Block akses ke ~/.openforge (protected)
forge > cat ~/.openforge/.env
ValueError: command accesses protected FORGE_HOME path (~/.openforge/)
forge > cat ~/.openforge/secrets/providers.json
Same — blocked.

# Terminal allowed workspace files
forge > ls forge-workspace/
✓ run_terminal_command (45ms): ["file.txt", "notes.txt"]
```

---

## Code Execution (HITL)

```bash
forge > Write a Python function to calculate factorial
AI: Here's a factorial function...

forge > Run it with code_execution
🔧 Preparing `code_execution` tool call...
   Code: def factorial(n): return n * factorial(n-1) if n > 0; print(factorial(5))
   Approval required: [y/n] y
✓ code_execution (250ms): exit code: 0\nstdout:\n120
```

---

## Performance Notes (Ornith on laptop)

- **Latensi tinggi adalah normal** untuk 9B quantized model di CPU (4 threads).
- `n-predict: -1` (unlimited) + ctx 16384 → bisa sangat lambat.
- Gunakan `max_tokens=512` di request untuk batasi panjang.
- `--cache-type-k q4_0 --cache-type-v q4_0` (quantized KV) sudah optimal.
- Prompt caching (`--prompt-cache F16`) sangat rekomendasi untuk iterasi.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Connection refused: 127.0.0.1:8080` | Pastikan `llama-server.exe` running |
| `Missing credentials` di Ornith | Set `api_key=dummy` (local provider) |
| Streaming lambat/diskip | Normal — laptop tua + model besar |
| `404 Not Found` di frontend | Pastikan backend `forge gateway start` running |
| `git grep "ghp_"` return secrets | Dokumentasitas saja (CONTINUATION_PROMPT.md) |

---

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
