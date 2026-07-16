# Nexa Agent — Project Worklog

> Source of truth for project state across development phases.
> Owned by: Nexa Architect flow. Last updated: 2026-07-16.

---

## Task ID: 1
Agent: Z.ai Code (main orchestrator)
Task: Build Nexa Agent v1.0.0 — a clean-room, web-based AI agent (Next.js 16) inspired by the Hermes Agent architecture, authored by Dearly Febriano Irwansyah. Implement core agent loop, tool registry, persistent memory, terminal-themed UI.

Work Log:
- Invoked the LLM skill to learn the z-ai-web-dev-sdk API (system prompts use role 'assistant'; thinking toggle; chat.completions.create).
- Created the Nexa core library under `src/lib/nexa/`:
  - `constants.ts` — NEXA_NAME, NEXA_VERSION (1.0.0), NEXA_AUTHOR, NEXA_HOME (~/.nexa), boot banner/sequence.
  - `types.ts` — NexaMessage, ProviderMessage, ToolSchema, ToolRequest, ToolResult, AgentStep, AgentTurnResult, NexaSession, NexaMemory.
  - `tools/base.ts` — abstract NexaTool contract.
  - `tools/registry.ts` — ToolRegistry (register/has/get/list/schemas/describe/execute with timing).
  - `tools/builtins.ts` — EchoTool, GetTimeTool, CalculateTool (safe recursive-descent parser, no eval), GenerateUuidTool, Base64Tool.
  - `tools/memory-tools.ts` — SaveMemoryTool, RecallMemoryTool, ListMemoryTool, ForgetMemoryTool.
  - `provider.ts` — LLMProvider wrapping z-ai-web-dev-sdk with a singleton client.
  - `memory.ts` — persistent memory CRUD (saveMemory/recallMemory/listMemory/deleteMemory/renderMemoryDigest) backed by Prisma.
  - `agent.ts` — NexaAgent core loop: assembles system prompt (identity + tool catalog + memory digest), calls LLM, parses tool calls (5-level tolerant parser), executes via registry, feeds results back, iterates until final answer or NEXA_MAX_TOOL_ITERATIONS.
- Prisma schema (`prisma/schema.prisma`): NexaSession, NexaMessage, NexaMemory. Ran `bun run db:push` — DB in sync.
- API routes:
  - `POST /api/chat` — runs one agent turn, persists user/tool/assistant messages, returns steps + answer.
  - `GET/POST /api/sessions` — list / create sessions.
  - `GET/PATCH/DELETE /api/sessions/[id]` — fetch-with-messages / rename / delete (cascade).
  - `GET/POST/DELETE /api/memory` — list / create / delete memories.
- UI (terminal-themed, emerald-on-dark, no indigo/blue):
  - `globals.css` — custom dark palette with emerald accents, scanlines, glow, blink cursor, custom scrollbar, grid background, fade-in animations.
  - `layout.tsx` — dark mode default, Nexa metadata, Geist Mono primary.
  - `page.tsx` — orchestrator: boot sequence → header → sidebar/transcript/composer/memory panel → sticky status bar.
  - Components: BootSequence (typewriter), Markdown (react-markdown + copyable code blocks), ToolStepView (collapsible tool call/result cards), MessageBlock (user/assistant/tool rendering), StatusBar (model/session/status), MemoryPanel (add/search/delete), Sidebar (sessions list), Composer (auto-resize textarea + suggestion chips), Transcript (messages + live pending steps + welcome screen).
- Fixed two bugs found during agent-browser verification:
  1. Transcript duplication after send → replaced optimistic append with authoritative reload from `/api/sessions/[id]`.
  2. Malformed `<tool_call>` markup leaking into answers → strengthened system prompt with a concrete worked example and built a 5-level tolerant parser (proper tags, unclosed tags, fenced JSON, bare JSON object, `tool(args)` shorthand) plus robust markup stripping.

Stage Summary:
- **Status: STABLE & FULLY FUNCTIONAL.** Lint clean (0 errors, 0 warnings). Dev server running on port 3000, `GET /` 200, all API routes 200.
- **Verified end-to-end with agent-browser:**
  - Multi-tool turn: "Calculate 256/8 then time in Tokyo" → agent called `calculate` then `get_time` in sequence, synthesized answer. ✅
  - Memory save: "remember my favorite language is TypeScript" → `save_memory` executed, persisted, panel shows it. ✅
  - Cross-session recall: new session "what's my favorite language?" → `recall_memory` found the preference, answered correctly. ✅
  - No duplication, no leaked markup. ✅
  - Mobile (390×844) responsive: hamburger drawer sidebar works. ✅
  - No console errors, no page errors. ✅
- Branding is 100% Nexa Agent / Dearly Febriano Irwansyah throughout (no references to any upstream project).

Unresolved Issues / Risks:
- None blocking. Tool-calling relies on prompt-based structured output (not native function-calling); the tolerant parser handles observed malformations, but edge cases with exotic model outputs could still occur. Mitigated by iteration cap + markup stripping.
- Memory digest is injected into every system prompt (capped at 24 items) — fine for now; could add semantic search later.

Priority Recommendations for Next Phase:
- Add more tools: web_search (via web-search skill), web_reader, file/notes CRUD, code execution sandbox.
- Add session rename UI (PATCH endpoint exists) and a "clear all" action.
- Add streaming responses for a more live feel (currently single round-trip per LLM call).
- Add a command palette (slash commands: /clear, /memory, /new).
- Add context compression when transcript exceeds a token threshold.
- Add light theme toggle (terminal dark is canonical, but a toggle is nice).
- Export/import sessions & memory as JSON.

---

## Task ID: 2
Agent: Z.ai Code (cron self-improvement cycle #1)
Task: Scheduled 15-min self-review. Assess project status, QA via agent-browser, fix bugs, add features, improve styling, update worklog.

Work Log:
- Read worklog.md (Task 1 complete: Nexa Agent v1.0.0 stable). Checked dev log — all 200s, no errors.
- QA via agent-browser: app loads clean, sessions intact, no console/page errors. Phase 1 stable.
- Invoked web-search skill to learn `zai.functions.invoke('web_search', ...)` API for a live web_search tool.

### New features added
- **Web tools** (`src/lib/nexa/tools/web-tools.ts`):
  - `WebSearchTool` — live web search via z-ai-web-dev-sdk `functions.invoke('web_search')`. Returns ranked results (title, url, snippet, domain, date). Caps payload.
  - `WebFetchTool` — reads a single URL's content via `functions.invoke('web_reader')` with HTML stripping + truncation.
  - Both registered in `createDefaultToolSet()` (agent now has 11 tools total).
- **Export-as-Markdown** (`src/app/api/export/[id]/route.ts`):
  - GET endpoint returns a session transcript as a downloadable `.md` file (user/assistant/tool messages, metadata header, collapsible tool outputs).
  - Wired to `/export` slash command + per-session download button in sidebar.
- **Slash command system** (`composer.tsx`):
  - Typing `/` opens a filterable command palette (arrow-key nav, Enter/Escape).
  - Commands: `/new`, `/clear`, `/memory`, `/export`, `/help` (renders a tools+commands reference card).
  - Handler wired in `page.tsx` via `handleCommand()`.
- **Session management** (`sidebar.tsx`):
  - Inline rename (edit icon → input → Enter to commit / Escape to cancel, optimistic update + PATCH).
  - Per-session export button (download icon → opens `/api/export/:id`).
  - "clear all" action with two-step confirm (click once → "confirm?" → click again → deletes all).
  - Session count badge + total message counter in footer.
  - Live pulse dot on the Nexa brand logo.

### Styling polish
- **Message timestamps**: user/assistant/tool messages now show HH:MM time beside the avatar.
- **Copy-answer button**: each assistant message has a one-click copy button.
- **Richer welcome screen**: 2×2 capability grid (web search, tool-calling, memory, terminal UX) + "try asking" examples + animated ping ring on the logo + MIT/attribution chip.
- **Thinking step-counter**: while working, shows "N tools called" badge + "awaiting result" cursor.
- **Sidebar**: session count badge, hover-revealed action icons (export/rename/delete), total-msg footer stat.
- **Composer**: updated placeholder ("type / for commands"), new web-search suggestion chip, command palette dropdown with hover highlight.

### Bug fixed
- **429 rate-limit failures**: discovered during web_search QA — the agent's 2nd LLM call (after tool execution) hit HTTP 429 "Too many requests", failing the whole turn. Added exponential-backoff retry (4 attempts: 1s→2s→4s→8s) in `LLMProvider.chatCompletion()` for transient errors (429, 5xx, rate-limit, timeout, ECONNRESET). After the fix, web_search turns complete successfully.

### Verification (agent-browser)
- Slash palette: typing `/` shows 5 commands, clickable. ✅
- `/help`: renders command table + full tool list. ✅
- **Web search**: "find a space exploration news headline" → agent called `web_search`, got live space.com result (SpaceX Starship V3 Starlink launch), synthesized answer with source. ✅
- Session rename: edit → "Space News Test" → committed (PATCH 200, title updated). ✅
- Export button present on each session. ✅
- Clear-all two-step confirm present. ✅
- Timestamps render on all messages. ✅
- Mobile (390×844): hamburger drawer + composer + slash palette all functional. ✅
- 0 page errors, 0 console errors. ✅
- Lint: 0 errors, 0 warnings. ✅

Stage Summary:
- **Status: STABLE & ENHANCED.** Nexa Agent now has live web access (search + fetch), a slash command system, session export/rename/clear-all, and richer terminal styling. The 429 retry fix makes the agent resilient to transient rate limits.
- Tool count: 11 (echo, get_time, calculate, generate_uuid, base64, save_memory, recall_memory, list_memory, forget_memory, web_search, web_fetch).
- All features verified end-to-end via agent-browser with real LLM + real web search calls.

Unresolved Issues / Risks:
- Web search adds latency (multi-round: LLM → search → LLM). Mitigated by retry logic, but a single turn can take 10–20s. Streaming responses would improve perceived performance.
- `web_reader` function availability depends on the SDK; if it's not present, WebFetchTool fails gracefully with an error message (no crash).
- Memory digest still injected into every prompt (capped 24). Semantic search is a future enhancement.

Priority Recommendations for Next Phase:
- **Streaming responses**: stream LLM output token-by-token for a live typing effect (big UX win).
- **Context compression**: summarize old messages when transcript exceeds a token threshold.
- **More tools**: notes/files CRUD, a code runner sandbox, image generation hook.
- **Keyboard shortcut overlay**: ⌘K command palette, ⌘N new session, ⌘B toggle sidebar.
- **Light theme toggle**: terminal dark is canonical; a toggle broadens appeal.
- **Session search**: full-text search across past sessions (SQLite FTS5).
- **Token/cost estimator**: show approximate token usage per turn in the status bar.

---

## Task ID: 3
Agent: Z.ai Code (user-directed Phase 2 + UI redesign + GitHub release)
Task: Implement file & terminal tools (Phase 2), redesign UI to ChatGPT/Z.ai style, integrate Nexa logo, prepare GitHub release with zip.

Work Log:
- **Backend Phase 2 — File & Terminal Tools**:
  - Created `src/lib/nexa/tools/fs-tools.ts` with 4 tools:
    - `ReadFileTool` — reads text files from a sandboxed workspace (path escape prevention, 100KB/4000-char caps)
    - `WriteFileTool` — writes files (creates parent dirs, overwrites existing)
    - `ListDirTool` — lists directory entries with file/folder icons
    - `RunTerminalCommandTool` — executes shell commands via `spawn` (15s timeout, 2000-char output cap, blocked dangerous patterns like `rm -rf /`, `mkfs`, `shutdown`)
  - Added `NEXA_WORKSPACE` constant (sandboxed to `nexa-workspace/` directory)
  - Added `getOpenAiSchemas()` method to `ToolRegistry` — returns OpenAI function-calling format (`{type:"function", function:{name, description, parameters}}`)
  - Registered all 4 new tools in `createDefaultToolSet()` → **18 tools total**
  - Wired `setActiveSessionId()` in chat API route so notes tools know the active session

- **UI Redesign — ChatGPT/Z.ai Style**:
  - Rewrote `globals.css` with the exact design system from user spec:
    - Dark: `--bg-primary:#0F0F0F`, `--bg-secondary:#181818`, `--bg-tertiary:#212121`, `--accent-primary:#4A9EFF`
    - Light: `--bg-primary:#FFF`, `--accent-primary:#2563EB`
    - Inter + JetBrains Mono fonts, 6/8/12/16px radius scale
  - Updated `layout.tsx`: Inter + JetBrains Mono via next/font, Nexa logo in metadata/icons/OG
  - Redesigned `sidebar.tsx`: clean brand header with logo, "New chat" pill button, search bar, sessions grouped by date (Today/Yesterday/Previous 7 Days/Older), hover-reveal export/rename/delete actions, footer with clear-all + author
  - Redesigned `message-block.tsx`: user messages as right-aligned rounded bubbles, assistant messages full-width (no bubble) with logo + name, per-message hover actions (copy/regenerate/like/dislike)
  - Redesigned `markdown.tsx`: code blocks with language label header + copy button, GitHub-flavored tables, styled links/headings/lists/blockquotes
  - Redesigned `tool-step.tsx`: collapsible tool-call cards with accent-subtle background, status dot (success/error), duration display
  - Redesigned `composer.tsx`: pill-shaped (24px radius), "+" menu button, auto-grow textarea, send button (accent circle), suggestion chips, "Nexa can make mistakes" hint
  - Redesigned `transcript.tsx`: empty state with large logo + "Halo, saya Nexa" greeting + tagline, thinking dots animation, tool-call counter badge
  - Redesigned `status-bar.tsx`: slim, model name, session id, message count, ready/running/error status
  - Redesigned `page.tsx`: 3-column layout (sidebar 260px + main + optional panels), slim header with editable title + model selector pill + ⌘K/theme/notes/memory toggles, removed boot sequence (clean ChatGPT-style)

- **Logo Integration**:
  - Copied `upload/nexa-agent.png` → `public/nexa-agent.png`
  - Used in: sidebar header, assistant message avatar, empty state, layout metadata (favicon, apple icon, OG image)

- **Bug Fix — Malformed JSON tool calls**:
  - The model produced `"arguments {` (missing colon) which broke JSON parsing
  - Added `repairJson()` function that fixes missing colons (`"key" {` → `"key": {`) and trailing commas
  - Updated `safeParseRequest()` to try strict JSON first, then repaired JSON
  - Fixed markup leakage: if `stripToolMarkup` returns empty (content was only malformed markup), return a clean fallback message instead of raw scaffolding
  - Updated shorthand regex to include all 18 tool names
  - Verified: agent successfully called `write_file` (wrote hello.txt) and `run_terminal_command` (ls -la + echo)

- **GitHub Release Preparation**:
  - Set git identity: `neuralforgeio` / `dearlyfebrianoi@gmail.com`
  - Created comprehensive `.gitignore` excluding: node_modules, .next, db/*.db, dev.log, nexa-workspace/, upload/, skills/, examples/, Caddyfile, test screenshots
  - Committed as `feat: Nexa Agent v1.0.0 — initial release` (31 files changed, 2082 insertions, 1352 deletions)
  - Created annotated tag `v1.0.0`
  - Added remote: `origin → https://github.com/neuralforgeio/nexa-agent.git`
  - Created `nexa-agent-v1.0.0.zip` (1.1MB) excluding all panel/runtime files
  - Verified: 0 panel-default files in git tree, logo included, all source files present
  - Note: push requires user authentication (old token compromised, not used)

Stage Summary:
- **Status: COMPLETE & RELEASE-READY.** Nexa Agent v1.0.0 has 18 tools (including real file & terminal operations), a polished ChatGPT/Z.ai-style UI with the Nexa logo, and is committed + tagged + zipped.
- **Verified end-to-end**: write_file creates real files in workspace, run_terminal_command executes shell commands (ls, echo), all UI components render correctly, 0 errors.
- Tool count: 18 (echo, get_time, calculate, generate_uuid, base64, save_memory, recall_memory, list_memory, forget_memory, web_search, web_fetch, save_note, list_notes, clear_notes, read_file, write_file, list_dir, run_terminal_command)
- Git: commit `ad2b4f9`, tag `v1.0.0`, remote `origin` set, zip `nexa-agent-v1.0.0.zip` ready.

Unresolved Issues / Risks:
- **GitHub push requires user action**: the previously-shared token is compromised and must not be used. User must create a new PAT and push. Instructions provided.
- Terminal tool runs real shell commands in the sandbox — powerful but requires trust in the agent. Mitigated by: workspace confinement, blocked dangerous patterns, timeout, output cap.
- `gh` CLI could not be installed (no root) — push must use raw git commands.

---
