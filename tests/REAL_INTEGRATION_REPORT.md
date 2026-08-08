# Nexa Agent — Real Integration Report (v4.0.0)

> Test runs performed on **2026-07-31** against:
> - **Local LLM**: Ornith-1.0-9b-Q4_K_M via llama.cpp server at `http://127.0.0.1:8080` (9B parameter model, running locally)
> - **Nexa backend**: `server.py` (FastAPI) at `http://127.0.0.1:8000`
> - **Web UI**: Next.js dev server at `http://127.0.0.1:3000`
> - **Workspace**: `C:\Users\Dearly Febriano\nexa-agent\forge-workspace`

---

## 1. Provider handshake

| Check | Result | Notes |
|---|---|---|
| Backend health (`GET /api/health`) | **PASS** | `{"status":"ok","version":"4.0.0", 33 tools listed}` |
| Provider list (`GET /api/provider`) | **PASS** | Active = `ornith` |
| Endpoint reachability (`GET /v1/models` on llama.cpp) | **PASS** | Model id: `.\Ornith-1.0-9b-Q4_K_M.gguf` |

---

## 2. Streaming & capability negotiation

| Scenario | Result | Evidence |
|---|---|---|
| SSE token streaming | **PASS** | `curl …/api/chat/stream` emitted `data: {"type":"token","text":"N"}`, `…"EX"`, `…"A"`, then `done`. |
| SSE keepalive pings | **PASS** | Observed `: ping` comments every ~15 s of inactivity, preventing browser disconnect during llama.cpp prompt processing. |
| Tools payload on a non-tool model | **FIXED** | When the provider answers 4xx "tools not supported", Nexa retries the same completion **without** the tools array. The observed `srv stop: cancel task` errors on llama-server stop. |

---

## 3. Tool orchestration — real (not mock)

End-to-end run of the user story: *"Create hello_e2e.py that prints `Nexa E2E Hello` and run it."*

Observed via `scripts/e2e_hello_world.py` against the live agent:

```
[TOOL:write_file] ok=True
    wrote 24 bytes to hello_e2e.py

[TOOL:run_terminal_command] ok=True
    exit code: 0
    stdout:
    Nexa E2E Hello
```

| Assertion | Result |
|---|---|
| File written to workspace | **PASS** |
| File content contains marker | **PASS** (`print('Nexa E2E Hello')`) |
| Terminal actually executed it | **PASS** (exit 0, stdout `Nexa E2E Hello`) |
| Assistant mentions marker in final answer | **PASS** |

**Tools actually invoked by the LLM:** `write_file`, `run_terminal_command`.

---

## 4. Frontend smoke

| Scenario | Result |
|---|---|
| `http://localhost:3000` serves v4.0 UI | **PASS** (page title, sidebar, sandbox visible) |
| Sidebar visible / sessions list | **PASS** |
| Sandbox panel toggle button | **PASS** (Ctrl+J) |
| Terminal panel — xterm.js initialized | **PASS** (WS connects to `ws://127.0.0.1:8000/ws/terminal`) |
| Working Process dropdown in message area | **PASS** (renders on assistant turns) |
| Console errors | None observed in happy path |

*Deeper visual verification intentionally performed via the host browser
(screenshots showed double sandbox/welcome-banner issues that are now
fixed).*

---

## 5. What still needs stress-testing

- Long tool chains (deep_research with 10+ searches).
- ``create_tool`` → immediate reuse path (scoped for v4.1).
- Windows edge cases: running under an account whose home path contains
  non-ASCII characters (lock-file creation has been tested with
  CJK-named profiles; not yet on Windows-1252 usernames).

---

## 6. Reproduce locally

```powershell
cd C:\Users\Dearly Febriano\nexa-agent

# 1. Start llama.cpp with any small GGUF (e.g. 3B).
.\llama-server.exe -m .\tiny.gguf --port 8080

# 2. Configure Nexa.
$env:NEXA_PROVIDER      = "llamacpp"
$env:NEXA_BASE_URL      = "http://127.0.0.1:8080/v1"
$env:NEXA_API_KEY       = "dummy"
$env:NEXA_MODEL         = "tiny.gguf"
$env:NEXA_LLM_SUPPORTS_TOOLS = "1"   # or 0 if your llama-server build lacks --jinja

# 3. Start fastapi backend + next dev.
.\.venv\Scripts\python.exe server.py         # port 8000
cd nexa_web; npm run dev                     # port 3000

# 4. Drive the agent end-to-end.
.\.venv\Scripts\python.exe scripts\e2e_hello_world.py
```

A green run prints ``E2E RESULT: PASS`` at the bottom.
