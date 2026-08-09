# OpenForge — 20-Feature Enterprise Roadmap (v3.1+)

> **Status**: Blueprint written. Execution deferred to v3.1.0+.
> Each feature has a specification, value, complexity (1-5), and dependencies.

## Categories

1. **Intelligence & Memory Core** (5 features)
2. **Tools & Automation** (5 features)
3. **UI/UX & Visualization** (5 features)
4. **Infrastructure & Enterprise** (5 features)

---

## 1. Intelligence & Memory Core

### 1.1 Semantic Vector Memory (Local RAG)
- **Description**: Replace the current FTS5 keyword search with semantic vector search (ChromaDB or FAISS) for true semantic recall. Fall back to TF-IDF if no vector backend.
- **Value**: Recall jumps from keyword-match to meaning-match. "How do I deploy?" finds docs about "shipping to production".
- **Complexity**: 4 (ChromaDB integration + embedding model + migration)
- **Dependencies**: None (additive)

### 1.2 Auto-Curated User Profile
- **Description**: The agent automatically writes `USER.md` from analysis of the user's message style, technical level, and preferences. No manual editing needed.
- **Value**: Personalized responses from turn 1, without the user configuring anything.
- **Complexity**: 3 (heuristic extraction + file writing)
- **Dependencies**: memory_files.py (exists)

### 1.3 Cross-Session Context Injection
- **Description**: When a new session starts, the agent auto-injects relevant context from past sessions (matched by topic similarity).
- **Value**: "Continue where we left off" works across sessions automatically.
- **Complexity**: 4 (topic clustering + context selection + prompt injection)
- **Dependencies**: 1.1 (Semantic Vector Memory)

### 1.4 Predictive Tool Chaining
- **Description**: The agent predicts the next tool call(s) pre-emptively based on the user's message, using the pattern_recognizer's history.
- **Value**: Faster responses (tools pre-warmed), better UX.
- **Complexity**: 5 (prediction model + pre-execution + rollback)
- **Dependencies**: pattern_recognizer.py (exists)

### 1.5 Local Knowledge Graph
- **Description**: Build a local knowledge graph from user interactions (entities + relationships). Query it via a `query_graph` tool.
- **Value**: The agent "understands" how concepts relate (e.g. "Forge uses Python + FastAPI + SQLite").
- **Complexity**: 5 (graph schema + extraction + query language)
- **Dependencies**: 1.1 (Semantic Vector Memory)

---

## 2. Tools & Automation

### 2.1 Web Search & Scraping Tool (enhanced)
- **Description**: Extend `web_search` to also fetch + parse the page content (via `web_reader` or httpx + readability-lxml). Save as markdown to the workspace.
- **Value**: Full web research, not just snippets.
- **Complexity**: 3 (httpx + HTML parsing + markdown conversion)
- **Dependencies**: web_search_tool.py (exists)

### 2.2 Project-Scoped Code Execution Sandbox (enhanced)
- **Description**: Add AST-based dangerous-call restriction on top of the existing project-scoped boundary + HITL.
- **Value**: Defense in depth — even if the user approves, AST blocking prevents `os.system('rm -rf /')`.
- **Complexity**: 4 (AST walker + call whitelist + sandbox escape detection)
- **Dependencies**: code_execution_tool.py (exists, v2.1.0)

### 2.3 Git Automation Tool
- **Description**: `git_tool` — auto-commit with semantic messages, PR creation, changelog generation.
- **Value**: Devs commit 10x/day; automating this saves real time.
- **Complexity**: 4 (git CLI wrapper + semantic message generation via LLM)
- **Dependencies**: run_terminal_command (exists)

### 2.4 File Diff & Patch Tool (enhanced rollback)
- **Description**: Extend `file_patch` with a rollback mechanism — keep a `.bak` history (last 5 versions) and a `revert` command.
- **Value**: Safety net for aggressive patching.
- **Complexity**: 2 (backup rotation + revert command)
- **Dependencies**: file_patch_tool.py (exists)

### 2.5 Background Process Manager (enhanced)
- **Description**: Enhance the background process manager with resource monitoring (CPU/memory), auto-restart on crash, and log streaming.
- **Value**: Long-running dev servers (npm run dev) stay alive and observable.
- **Complexity**: 4 (psutil + supervisor loop + log tail)
- **Dependencies**: terminal_tool.py (exists)

---

## 3. UI/UX & Visualization

### 3.1 Web Terminal Panel (xterm.js) — full version
- **Description**: Replace the minimal TerminalPanel with xterm.js for full ANSI color + escape sequence support.
- **Value**: Real terminal experience in the browser.
- **Complexity**: 3 (xterm.js + addons + WebSocket glue)
- **Dependencies**: /ws/terminal (exists, v3.0.0)

### 3.2 Artifact Panel
- **Description**: A right-side panel that renders code, HTML, SVG, and Markdown artifacts in real-time as the agent generates them.
- **Value**: "Show me the UI" → instant preview without copy-paste.
- **Complexity**: 5 (live render + sandbox iframe + multi-format)
- **Dependencies**: None

### 3.3 Tool Process Visualization
- **Description**: Multi-step progress bar + log streaming for tool execution (e.g. "Step 2/4: Running tests… [streaming output]").
- **Value**: Transparency for long-running tool chains.
- **Complexity**: 3 (progress state + streaming UI)
- **Dependencies**: ThinkingIndicator (exists)

### 3.4 Thinking Mode Panel
- **Description**: Collapsible reasoning chain panel that shows the agent's step-by-step reasoning before the final answer.
- **Value**: Trust + debuggability — see *why* the agent answered.
- **Complexity**: 3 (reasoning_chain.py integration + UI)
- **Dependencies**: reasoning_chain.py (exists)

### 3.5 Ask Question Mode
- **Description**: A toggle for "quick Q&A" mode — no tool calling, instant text response (for simple questions).
- **Value**: 10x faster responses for "what's the capital of France?".
- **Complexity**: 2 (flag + skip tool dispatch)
- **Dependencies**: conversation_loop.py (exists)

---

## 4. Infrastructure & Enterprise

### 4.1 MCP (Model Context Protocol) Client
- **Description**: Support external MCP plugins (Google Drive, Slack, GitHub) as additional tools.
- **Value**: Connect the agent to the user's existing tools/services.
- **Complexity**: 5 (MCP client + plugin discovery + tool mapping)
- **Dependencies**: tools/registry.py (exists)

### 4.2 Provider Failover & Smart Routing (enhanced)
- **Description**: Enhance the v2.0 failover with complexity-based routing — simple questions go to a cheap/fast model, complex ones to a powerful model.
- **Value**: 50-80% cost reduction without quality loss.
- **Complexity**: 4 (complexity classifier + routing rules + cost tracking)
- **Dependencies**: provider_failover.py (exists, v3.0.0 wired)

### 4.3 Trajectory Export (JSONL)
- **Description**: Save the full prompt → tool → response trajectory as JSONL for fine-tuning datasets.
- **Value**: Build a training dataset from real usage.
- **Complexity**: 3 (event logging + JSONL serializer)
- **Dependencies**: conversation_loop.py (exists)

### 4.4 Self-Healing Dependency Manager
- **Description**: When a tool fails with `ImportError` or `ModuleNotFoundError`, auto-install the missing package (with HITL approval).
- **Value**: "It just works" — no manual `pip install`.
- **Complexity**: 3 (error classification + pip subprocess + approval)
- **Dependencies**: self_healer.py (exists)

### 4.5 Observability Dashboard
- **Description**: A DevTools panel showing raw JSON prompts, latency per tool, token usage, and memory profiling (tracemalloc).
- **Value**: Debug performance + cost issues.
- **Complexity**: 4 (instrumentation + UI + memory profiling)
- **Dependencies**: None

---

## Execution Plan (5 Phases × 4 Features)

| Phase | Features | Est. Effort |
|-------|----------|-------------|
| v3.1.0 | 1.1, 2.4, 3.5, 4.3 | Medium |
| v3.2.0 | 1.2, 2.1, 3.4, 4.4 | Medium |
| v3.3.0 | 1.3, 2.3, 3.3, 4.2 | High |
| v3.4.0 | 1.4, 2.5, 3.1, 4.5 | High |
| v3.5.0 | 1.5, 2.2, 3.2, 4.1 | Very High |

---

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
