# Nexa Agent v4.0.0 — Punch List (What Was Reported vs What Was Fixed)

> Cross-reference between the screenshots you shared, the reported bugs, and
> the actual code-level root causes.

## A. Bugs you observed in the screenshots

### 1. "Hai" answered twice (double bubble, same text)

**Root cause.** Two things combined:

1. `SandboxPanel`'s dev-server autodetect listed `http://localhost:3000` —
   which is the Nexa UI *itself*. So the sandbox iframe loaded Nexa inside
   Nexa, and the iframe-then-parent paint raced. (This is the "sandbox
   membuka website itu sendiri" bug you spotted.)
2. The terminal welcome banner used UTF-8 box-drawing characters
   (`╔═║╚╝`); in xterm.js 6 on Windows/Turbopack they render as a column of
   identical glyphs (`YYYYY…`). That made the *terminal* look like it was
   double-printed, which in turn made the Page component look like it had
   two copies of the panel.

The actual chat duplication also existed because the previous chat
connection retried once after the first response landed (SSE reconnect
backoff firing on a clean `done` event).

**Fix (all three).**

- `SandboxPanel.tsx` — `detectPreview()` now **skips nexa's own port** and
  only auto-opens when a *dev server on a different port* is listening, OR
  when the workspace contains a previewable file the user actually
  selected. Sandbox starts **closed** by default; you toggle it with the
  top-right icon (or `Ctrl+J`).
- `TerminalPanel.tsx` — the banner is pure ASCII now; PTY reconnect loop
  with exponential backoff; the panel is **not** mounted twice.
- `lib/stream.ts` — on `type === "done"` we now close the stream and do
  NOT retry; retries only happen on actual network errors or 5xx.

### 2. Sandbox iframe showed the Nexa UI itself

**Fix in place (see above).** Additionally: the sandbox's workspace-path
input lets you type a relative path (e.g. `ecommerce/index.html`) to
preview any file from `NEXA_WORKSPACE` directly.

### 3. Terminal was full of strange characters, and wouldn't accept input

**Fix.** Two independent bugs:

- The ASCII banner had a UTF-8 border (now ASCII).
- The WebSocket URL used to hit `ws://localhost:3000/ws/terminal`, which
  Next.js refused to proxy. Now we connect **directly** to the FastAPI
  backend: `ws://127.0.0.1:8000/ws/terminal`. With that single line,
  stdin/stdout flows exactly like a local console.
- Added **auto-reconnect with exponential backoff** (2 s → 4 s → 8 s…)
  so a backend restart doesn't leave the terminal stuck at "disconnected."

### 4. UI still looks old ("old theme")

**Fix (style polish, v4.0.0 patch).**

- Background is now `#0D0E10` globally (matches your dark vision).
- The empty-state greeting has been elevated to z.ai-style centered
  typography with the Nexa rhombus logo.
- Quick-action chips have been rewritten to the four "builder" tasks
  (Build landing page / Run code / Search web / Analyze a file).
- Sidebar gains Ctrl+B toggle; panel width 264 px; smoother borders.
- Working Process dropdown now contains **two** nested levels:
  **Thought Process** ⊂ Working Process — exactly like your sketch.

### 5. llama.cpp "auto-cancel" (`srv stop: cancel task`)

**Fix.** llama-server's task-cancellation fires when the request payload
contains a `tools` array the model build can't handle. Nexa now:

1. Sends tools normally.
2. On a 4xx "tools not supported" response, **retries once without tools**.
3. Emits a lightweight SSE keepalive ping every 15 s so the browser doesn't
   close the connection during long prompt processing.

End-to-end validated: the earlier curl captured streaming tokens
(`NEXA E2E OK`, `Hello` → `Halo! 👋 Ada yang bisa saya bantu hari ini?`).

---

## B. New features (v4.0.0 preview)

- **20 planning tools** under `tools/planning/` (see `.plans/PLANNING_TOOLS_20.md`).
- **`create_tool`** — the agent can extend itself by writing new tools
  into `~/.nexa/tools/` (loaded next turn).
- **`task_plan` / `plan_and_delegate`** — full decomposition workflow.
- **PTY terminal** in the sandbox (xterm.js, real shell, workspace cwd).
- **Web Preview**: iframe `html/css/js` from workspace, or auto-detected
  dev server.
- **Working Process → Thought Process** nested dropdown.
- **User-scaffolded content**: `~/.nexa/USER.md`, `~/.nexa/PROCEDURES.md`
  are injected into every system prompt — personalization without editing code.
- **Global CLI install** — `pip install -e .` puts `nexa` / `nexa-chat`
  on `%USERPROFILE%\AppData\Roaming\Python\Python313\Scripts\` (PATH added).

---

## C. Deferred to v4.1

- Full folder re-org under `agent/{core,memory,intelligence,system}` —
  planned in `.plans/FILE_ORGANIZATION.md`. The public API
  (`import agent…`) stays stable during migration, so this is a non-
  breaking refactor once we schedule it.
- WebSocket multiplexing (single `/ws/*` route handler) — currently the
  terminal backend lives on port 8000 while the frontend lives on 3000.
  For v4.1 we plan to bind them behind a tiny reverse proxy so only one
  port needs to be exposed.
- Diff-view in `file_patch` tool cards (showing changed lines inline).
