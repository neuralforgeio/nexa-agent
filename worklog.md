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
