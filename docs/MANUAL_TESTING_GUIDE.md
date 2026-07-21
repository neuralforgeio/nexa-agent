# Nexa Agent — Manual Testing Guide

> **Version**: v3.0.0+ | **Creator**: Dearly Febriano Irwansyah | **License**: MIT

Panduan lengkap untuk menguji Nexa Agent secara manual: instalasi, konfigurasi
provider, CLI, TUI, Web UI, dan skenario end-to-end.

---

## Daftar Isi

1. [Instalasi](#1-instalasi)
2. [Konfigurasi Provider](#2-konfigurasi-provider)
3. [Testing CLI](#3-testing-cli)
4. [Testing TUI](#4-testing-tui)
5. [Testing Web UI](#5-testing-web-ui)
6. [Testing Terminal Security](#6-testing-terminal-security)
7. [End-to-End Scenarios](#7-end-to-end-scenarios)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Instalasi

### Linux / macOS (curl one-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
```

Atau dengan wget:

```bash
wget -qO- https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.sh | bash
```

### Windows (PowerShell irm one-liner)

Buka **PowerShell** (bukan Command Prompt), lalu:

```powershell
irm https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 | iex
```

Atau simpan dan jalankan:

```powershell
iwr https://raw.githubusercontent.com/neuralforgeio/nexa-agent/main/scripts/install.ps1 -OutFile install.ps1
.\install.ps1
```

### Verifikasi Instalasi

Setelah instalasi selesai, buka terminal baru (agar PATH terupdate) dan:

```bash
nexa --help         # menampilkan help dengan rich table
nexa doctor          # menjalankan self-health diagnostics
nexa provider list   # menampilkan 8 provider yang tersedia
```

Output yang diharapkan dari `nexa provider list`:

```
 Providers
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Name     ┃ Base URL                              ┃ Model                   ┃ Key      ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ → openai │ https://api.openai.com/v1             │ gpt-4o                  │ (env)    │
│   openro │ https://openrouter.ai/api/v1          │ anthropic/claude-3.5-s │ (env)    │
│   ollama │ http://localhost:11434/v1             │ llama3.2                │ (env)    │
│   llamac │ http://localhost:8080/v1               │ local-model             │ (env)    │
│   lmstud │ http://localhost:1234/v1              │ loaded-model            │ (env)    │
│   vllm   │ http://localhost:8000/v1              │ meta-llama/Llama-3.1-8B │ (env)    │
│   tokenr │ https://api.tokenrouter.io/v1        │ auto:balance            │ (env)    │
│   databr │ (set NEXA_BASE_URL)                   │ databricks-claude-sonne │ (env)    │
└──────────┴────────────────────────────────────────┴─────────────────────────┴──────────┘
```

---

## 2. Konfigurasi Provider

### Opsi A: TokenRouter (recommended — OpenAI-compatible routing gateway)

1. Daftar di https://tokenrouter.io/signup
2. Console → API Keys → create, copy nilai `tr_...` (hanya ditampilkan sekali!)
3. Tambahkan ke Nexa:

```bash
nexa provider add tokenrouter
# ? API key (input hidden): tr_paste_key_here
# ? Model ID [auto:balance]:           # tekan Enter untuk default
✓ Saved tokenrouter to ~/.nexa/secrets/providers.json
```

4. Aktifkan:

```bash
nexa provider use tokenrouter
✓ Switched to tokenrouter (https://api.tokenrouter.io/v1)
```

5. Test koneksi:

```bash
nexa provider test tokenrouter
✓ tokenrouter is healthy (responded 200).
```

### Opsi B: OpenAI (langsung)

```bash
export OPENAI_API_KEY="sk-..."        # Linux/macOS
$env:OPENAI_API_KEY = "sk-..."        # Windows PowerShell

nexa provider use openai
nexa provider test openai
```

### Opsi C: Ollama (local, gratis, no API key)

1. Install Ollama dari https://ollama.com
2. Pull model:

```bash
ollama pull llama3.2
```

3. Tambahkan ke Nexa:

```bash
nexa provider add ollama
# ? API key (input hidden): dummy    # Ollama menerima key apa saja
# ? Model ID [llama3.2]:             # tekan Enter
nexa provider use ollama
```

### Opsi D: Custom endpoint (apapun yang OpenAI-compatible)

```bash
nexa provider add my-custom-llm \
  --base-url "https://my-llm.example.com/v1" \
  --api-key "sk-mykey" \
  --model "my-model-v1"

nexa provider use my-custom-llm
```

---

## 3. Testing CLI

### 3.1 Interactive REPL (chat)

```bash
nexa-chat
```

Anda akan melihat banner Nexa Agent + prompt `nexa >`. Ketik pesan:

```
nexa > Hello, what can you do?
nexa > Read the file nexa-workspace/notes.txt and summarize it
nexa > /help                         # tampilkan semua slash commands
nexa > /tools                        # tampilkan 10 tools tersedia
nexa > /provider list                # tampilkan semua provider
nexa > /provider use ollama          # switch provider runtime
nexa > /model llama3.2               # ganti model
nexa > /doctor                       # self-health check
nexa > /memories                     # tampilkan accumulated memories
nexa > /exit                         # keluar (atau Ctrl+D)
```

### 3.2 Single-shot (non-interactive)

```bash
nexa-agent "What is the capital of France?"
```

Output streaming ke stdout (token-by-token).

### 3.3 Subcommands

```bash
nexa setup                  # initialize ~/.nexa/
nexa doctor                  # self-health diagnostics
nexa model llama3.2          # set model
nexa model                   # show current model
nexa gateway start           # start backend server (port 8000)
nexa gateway start --port 9000  # custom port
nexa gateway stop            # stop server (graceful SIGTERM)
nexa gateway status          # check if running
nexa provider list           # list all providers
nexa provider add tokenrouter    # interactive add
nexa provider use tokenrouter    # switch active
nexa provider test openai    # health check
nexa provider remove tokenrouter  # delete
```

---

## 4. Testing TUI

### 4.1 Start TUI

```bash
python -m ui_tui.app
```

Atau (jika entry point terinstall):

```bash
nexa-tui
```

### 4.2 Layout

Anda akan melihat layout multi-pane:

```
┌─ Nexa Agent v3.0.0 │ model: gpt-4o │ tokens: ~0 │ server: DOWN │ 14:32 ─┐
├──────────────────────────────────────┬─────────────────────────────────────┤
│                                      │ Tool Log:                           │
│ Hello, I'm Nexa. Type a message...  │                                     │
│                                      │ (No tool calls yet.)                │
│                                      │                                     │
├──────────────────────────────────────┴─────────────────────────────────────┤
│ nexa > _                                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Test slash commands di TUI

```
nexa > /help                        # tampilkan commands tersedia
nexa > /provider list               # list providers di tool log pane
nexa > /provider use tokenrouter    # switch provider
nexa > /provider test openai        # health check
nexa > /model gpt-4o                # ganti model (update status bar)
nexa > /doctor                      # health check
nexa > Hello, tell me about yourself # kirim pesan ke AI
nexa > /exit                        # keluar (atau Ctrl+C)
```

### 4.4 Verifikasi streaming

Saat AI menjawab, token akan muncul satu per satu di chat area. Jika AI
memanggil tool, akan muncul card di tool log pane:

```
✓ read_file (45ms)
  path: nexa-workspace/notes.txt
✓ write_file (120ms)
  path: nexa-workspace/output.txt
```

---

## 5. Testing Web UI

### 5.1 Start backend + frontend

```bash
# Terminal 1: backend (Python)
nexa gateway start
# atau: .venv/Scripts/python.exe server.py    (Windows)
# atau: .venv/bin/python server.py            (Linux/macOS)

# Terminal 2: frontend (Next.js)
cd nexa_web
npm install        # hanya pertama kali
npm run dev
```

### 5.2 Buka browser

Buka http://localhost:3000

Anda akan melihat:
- **Empty state**: logo Nexa + "Hello, I'm Nexa" + 4 quick-action chips
- **Sidebar kiri**: New Chat + History (kosong di awal)
- **Composer pill**: input box di bawah

### 5.3 Test chat

1. Ketik "Hello, what can you do?" di composer → Enter
2. Streaming token akan muncul di chat area
3. Jika AI call tool, akan muncul **collapsible tool call card** di bawah
   pesan assistant (klik untuk expand/collapse result JSON)
4. Setelah selesai, tool call cards tetap ada (persisted) — reload halaman
   untuk verify

### 5.4 Test Settings Panel (gear icon)

1. Klik **gear icon (⚙)** di footer sidebar kiri
2. Modal "LLM Providers" muncul dengan 8 provider
3. Klik **"Add Provider"**:
   - Name: `tokenrouter`
   - Base URL: `https://api.tokenrouter.io/v1`
   - API key: `tr_your_key` (password field — tersembunyi)
   - Model: `auto:balance`
   - Centang "Activate immediately"
   - Klik **Add**
4. Provider baru muncul di list dengan badge **ACTIVE**
5. Klik **Test** pada provider untuk health check

### 5.5 Test Terminal Panel

1. Klik **terminal icon (▰)** floating di kanan bawah
2. Bottom panel terminal muncul (collapsible)
3. Ketik `echo hello` → Enter
4. Output muncul: `hello`
5. Ketik `ls nexa-workspace/` → lihat file di workspace
6. Ketik `clear` → clear terminal
7. Klik chevron-down untuk collapse, atau X untuk close

### 5.6 Test mobile responsive

1. Buka DevTools (F12) → toggle device toolbar (Ctrl+Shift+M)
2. Pilih iPhone 12 (390x844)
3. Hamburger menu muncul di header
4. Klik hamburger → sidebar drawer terbuka dengan backdrop
5. Pilih session → drawer tertutup otomatis

### 5.7 Test SSE reconnect

1. Mulai chat dengan AI
2. Saat streaming, **matikan backend** (Ctrl+C di terminal server.py)
3. Browser akan tampilkan "Connection lost. Reconnecting..."
4. Setelah 4 attempts (1s+2s+4s+8s), muncul error message
5. Restart backend → kirim pesan baru → works again

---

## 6. Testing Terminal Security

### 6.1 Verify ~/.nexa access blocked

Di Web UI terminal panel atau CLI:

```bash
nexa > run_terminal_command with command: cat ~/.nexa/.env
```

Expected: **BLOCKED** dengan pesan:
```
ValueError: command accesses protected NEXA_HOME path (~/.nexa/).
Terminal commands cannot read or write files inside NEXA_HOME to prevent
API key / secrets exfiltration.
```

### 6.2 Verify other blocked patterns

```bash
cat ~/.nexa/memory/MEMORY.md          # BLOCKED
cat ~/.nexa/nexa.db                    # BLOCKED
cat ~/.nexa/secrets/providers.json     # BLOCKED
echo "x" > ~/.nexa/.env                # BLOCKED
cat $HOME/.nexa/.env                   # BLOCKED
cat $NEXA_HOME/.env                    # BLOCKED
```

### 6.3 Verify legitimate commands allowed

```bash
echo hello                             # ALLOWED
ls nexa-workspace/                     # ALLOWED
cat nexa-workspace/notes.txt           # ALLOWED (inside workspace)
```

### 6.4 Python test

```python
import asyncio
from tools.terminal_tool import run_terminal_command

async def test():
    # Should BLOCK
    try:
        await run_terminal_command("cat ~/.nexa/.env")
        print("BREACH!")
    except ValueError as e:
        print(f"BLOCKED OK: {e}")

    # Should ALLOW
    result = await run_terminal_command("echo hello")
    print(f"Allowed: {result}")

asyncio.run(test())
```

---

## 7. End-to-End Scenarios

### 7.1 Scenario: Write + Read file

```
User: Create a file called hello.txt with content "Hello from Nexa!"
AI: [calls write_file tool]
    ✓ write_file (45ms)
    "wrote 17 bytes to hello.txt"

User: Now read it back to me
AI: [calls read_file tool]
    ✓ read_file (12ms)
    The file contains: "Hello from Nexa!"
```

### 7.2 Scenario: Web search

```
User: What's the latest version of Python?
AI: [calls web_search tool]
    ✓ web_search (1234ms)
    The latest stable version of Python is 3.13.3...
    Source: https://www.python.org/downloads/
```

### 7.3 Scenario: Code execution (with HITL approval)

```
User: Calculate 2^10 using Python
AI: [calls code_execution tool with requires_approval=True]
    🔧 Code execution awaiting approval:
    print(2 ** 10)

    [In TUI/Web UI: user sees code + y/n prompt]
    User: y

    ✓ code_execution (250ms)
    exit code: 0
    stdout: 1024
```

### 7.4 Scenario: Provider failover

```bash
export NEXA_FAILOVER_ENABLED=1
export NEXA_FAILOVER_CHAIN=tokenrouter,openai,ollama

nexa-chat
nexa > Hello!
# If tokenrouter fails 3x → auto-switch to openai → auto-switch to ollama
```

### 7.5 Scenario: Memory persistence

```
Session 1:
nexa > My name is Dearly and I prefer Python over JavaScript
AI: [curates memory → USER.md updated]

Session 2 (new chat):
nexa > What's my name and what language do I prefer?
AI: Your name is Dearly, and you prefer Python over JavaScript.
    (memory injected from USER.md)
```

---

## 8. Troubleshooting

### "nexa: command not found"

Setelah install, buka terminal baru. Jika masih tidak ketemu:

```bash
# Linux/macOS
echo 'export PATH="$HOME/nexa-agent/.venv/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Windows PowerShell
$env:Path += ";$HOME\nexa-agent\.venv\Scripts"
```

### "OPENAI_API_KEY not set"

Anda perlu configure provider dulu:

```bash
nexa provider add tokenrouter   # atau openai, ollama, dll
nexa provider use tokenrouter
```

### "Connection refused" di Web UI

Backend tidak running. Start:

```bash
nexa gateway start
# atau
.venv/Scripts/python.exe server.py    # Windows
.venv/bin/python server.py             # Linux/macOS
```

Verifikasi: `curl http://localhost:8000/api/health` → harus 200 OK.

### Frontend "npm run build" gagal di Windows

Bug Turbopack Next.js 16 di Windows. Workaround:

```bash
cd nexa_web
npm run dev    # dev mode bekerja sempurna
```

Atau downgrade Next.js ke 15:

```bash
npm install next@15
# Rename next.config.ts → next.config.js (Next 15 tidak support .ts)
```

### Memory tidak di-inject ke prompt

Verify memory files ada:

```bash
cat ~/.nexa/memory/MEMORY.md
cat ~/.nexa/memory/USER.md
```

Jika kosong, chat beberapa turn dulu — memory curator butuh data untuk curate.

### Terminal security terlalu ketat (false positive)

Beberapa command legitimate mungkin terblokir karena mengandung substring
`.nexa`. Contoh:

```bash
echo "this is about .nexa documentation"   # MUNGKIN terblokir
```

Workaround: hindari substring `.nexa` di command, atau edit
`tools/terminal_tool.py` `_PROTECTED_PATH_PATTERNS` untuk fine-tune.

---

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
