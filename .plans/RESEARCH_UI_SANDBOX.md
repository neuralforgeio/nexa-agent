# OpenForge — Research: UI + Sandbox patterns (v4.0.0)

Comparison of the dominant AI-native chat surfaces, focused on what they do
for *thinking transparency*, *code execution*, and *in-chat previews*.

Sources: Claude.ai (web), ChatGPT (web), GLM 5.2 (z.ai), Codex / Cursor,
v0 by Vercel.

---

## 1. Thinking transparency ("Thought Process")

### Claude.ai
- A dedicated "thinking" disclosure on each assistant turn, collapsed by
  default once done. While streaming it shows a pulsing dot + truncated
  thought tail. Once done the header becomes "Thought for N seconds —
  click to expand".
- Inside, each thought is a separate block in monospace-ish styling.

### ChatGPT (o-series / GPT-5 thinking)
- Renders a compact chip that reads "Thinking" while in progress, then
  swaps to "Thought for Xs" on completion. Expanding shows a scrollable
  step list with icons per step type (analysis, web-browse, code).

### Z.ai / GLM
- "Work" panel lists major actions (Search, Read, Generate) as expandable
  rows; thinking is embedded as an indented sub-item.

### Best hybrid for Forge
``Working Process`` panel (outer, expanded while running), and nested
``Thought Process`` (inner, auto-collapsed once done). Bottom line: the
**outer** shows tool calls + results, the **inner** shows the model's
reasoning chain.

---

## 2. Sandbox / artifact panels

### Claude.ai "Artifacts"
- When the model emits a runnable artifact (HTML / React component / Mermaid
  diagram / SVG), the right sidebar opens automatically with the artifact
  rendered. Artifacts are isolated from the chat thread (own version
  history). Editing the artifact updates it in place and forks a version.

### ChatGPT "Canvas"
- A split-panel toolkit for long-form editing — writing or code — that
  opens on demand. Not an arbitrary-URL previewer. Diff UI for revisions.

### Vercel v0
- The preview iframe *is* the product surface. Chat on the left, rendered
  app on the right. The preview is always a real URL on a real CDN, so
  refresh = new deploy. Forge's local version of this: serve the workspace
  file through ``/api/sandbox/preview`` (no build step needed for HTML).

### Best hybrid for Forge
Keep the sandbox right-sidebar but make it *content-aware*:
  - If the workspace has an active dev server on a non-Forge port → iframe it.
  - Otherwise → iframe ``/api/sandbox/preview`` of the current file
    (defaulting to ``index.html`` if the user just asked for a website).
  - If neither → show a helpful empty state ("Ask Forge to build a web
    project") and leave the panel CLOSED unless the user opened it.

The current v3 default of "load localhost:3000 when no project exists"
recursively renders Forge inside Forge — fixed in v4.0.0.

---

## 3. Terminal integration

### Cursor / Cline
- ``xterm.js`` terminal embedded in a collapsible bottom panel. PTY is
  connected to the workspace root (the directory the editor has open).
  Output streams token-by-token via ANSI escape codes.
- "Run in terminal" action per suggested command — one click, real
  keystrokes, real scrollback.

### Replit Agent
- Same xterm.js, but the panel is always visible in a bottom strip and
  its content persists across sessions via a session-store.

### Best hybrid for Forge
- PTY lives on the backend (``server.py``).
- Frontend talks WebSocket → backend pipes to winpty (Windows) / ptyprocess
  (POSIX).
- Terminal sits in the bottom half of the Sandbox on the right.
- ANSI welcome banner is ASCII-only (avoid the tofu boxes).

---

## 4. Streaming UX

All four surfaces show tokens as soon as they're generated. ChatGPT adds
a subtle "stop generating" button. Both Claude and ChatGPT smooth-scroll
to the bottom while keeping the scrollable region snappy (momentum
scroll).

### Forge
Our SSE layer already streams deltas (verified end-to-end through
llama.cpp). The remaining work is Surfacing:
- A **live-token cursor** next to the incomplete message (``ThinkingIndicator``).
- A **stop button** that sends ``DELETE /api/chat/stream`` (cancels the
  server-side generator) — nice-to-have, deferred.
- Smaller monospace for tool-log lines so a big ``search_files`` result
  doesn't dominate the layout.

---

## 5. Design tokens (v4.0.0)

```ts
// lib/theme.ts (target)
background.primary   #0D0E10   // main chat area
background.secondary #141618   // panels (sidebar, sandbox)
background.tertiary  #1A1B1E   // elevated cards
border.subtle        #24262B
border.accent        rgba(74,158,255,0.25)
text.primary         #ECECEC
text.secondary       #9A9A9A
text.tertiary        #6A6A6A
accent.primary       #4A9EFF
accent.hover         #3A8EEF
success              #4ADE80
warning              #FBBF24
error                #F87171
info                 #22D3EE
```

Typography: Inter for UI, JetBrains Mono for code/terminal.
Border radius: 8px base, 12px cards, 20px composer, 999px pills.
Motion: 150–250 ms ease-out transitions; 2 deliberate animations (thinking
dots, working-process chevron spin).

---

## 6. Action items (translated into the codebase)

| Research insight | Code change |
|---|---|
| Claude artifacts = right panel | `components/SandboxPanel.tsx` — already a right panel since v4.0.0 |
| ChatGPT thought-summary | `components/WorkingProcess.tsx` — auto-collapse + summary line |
| v0 = always-preview | `/api/sandbox/preview` with dev-server autodetect + workspace fallback |
| Cursor = workspace PTY | `components/TerminalPanel.tsx` real-PTY via winpty |
| Clean ASCII banner | TerminalPanel banner rewritten in pure ASCII |
