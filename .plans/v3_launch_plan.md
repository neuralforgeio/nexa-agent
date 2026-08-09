# OpenForge — MASTER PRODUCT FLAGSHIP PLAN (v3.0.0 → v4.0.0)

> **Owner**: Dearly Febriano Irwansyah
> **Vision**: Forge menjadi local AI agent kelas enterprise — autonomous,
> programmer-centric, full-featured, dengan sandbox lengkap + deep research
> + tool chaining. Orang lain bisa install dengan satu baris curl/irm dan
> dalam 60 detik punya agent yang lebih baik dari GPT-4 biasa.

---

## 🎯 Phase A: Launcher (curl/irm) + Installer (DONE ✓)

- [x] Ultra-cool installer with animations, progress bars, unicode sparkles
- [x] Cross-platform (Linux/macOS + Windows/PowerShell)
- [x] Auto-detect / install Python 3.11+, uv, git
- [x] Auto-clone repo, create venv, install deps, run `forge setup`
- [x] Instruction message after install (new terminal + PATH)

## 🎯 Phase B: Frontend UI Polish + Sandbox Layout

**Layout redesign**:

```
┌──────────────────────────────────────────────────────────────────┐
│ TopBar: [WInexaLogo] [Provider: Ornith] [Mode: Chat] [⚡Flash] │
├──────────────┬──────────────────────────────────┬───────────────┤
│ Sidebar      │ Main Chat                        │ Sandbox      │
│ ──────────   │                                  │ ──────────    │
│ + History    │  (Chat area with streaming)      │               │
│ + Sessions   │                                  │ ┌─────────┐   │
│ + Agents     │  Tool cards (collapsible)        │ │ Terminal │  │
│ + Personas   │                                  │ │          │  │
└──────────────┴──────────────────────────────────┘ └───────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### B1: Sidebar + Quick Action Chips
- Collapsible sidebar (Ctrl+B toggle)
- 4 quick-action chips below composer (Write Code / Search Web / Analyze File / Explain)
- Session history with delete-on-hover
- Session rename (inline edit)

### B2: Sandbox Right Panel (50% width default)
- **Preview pane** (top): iframe rendering HTML/CSS/JS output
- **Terminal pane** (bottom): xterm.js or minimal, with:
  - AI-controlled command execution
  - Auto-complete commands
  - Real-time output streaming
- **Split resize** (drag between them)
- **Close-able** (X icon collapses to 0 width)

### B3: Center Chat Polish
- ChatGPT-style message bubbles
- Streaming cursor (blinks during generation)
- Markdown rendering (code syntax block + tables + lists)
- Copy button per message
- Token count per message
- Regenerate button (rotating icon) with reasoning chain

## 🎯 Phase C: Agent Intelligence (Priority Order)

### C1: Deep Research Agent ✅ DONE
- Automatically when user asks something fresh
- Multi-query reformulation → DuckDuckGo → fetch pages → extract facts → validate → synthesize
- Writes findings to knowledge cache (`~/.openforge/knowledge/`)
- `/deep-search <query>` command available in CLI
- Add 'deep_research' tool (id: 11) in registry

### C2: Ask Question Mode ✅ DONE
- Simple factual questions use fast path (no tools)
- `should_use_quick_mode()` heuristic
- Long technical questions fallback to tools

### C3: Tool Chaining via Suggestion Chips
- After tool result, show suggestion chips as next steps:
  - "Run tests" → `run_terminal_command("npm test")`
  - "Explain this code" → `read_file("path") then summarize�``
  - "Create variation" → `file_patch(...)`
- Smart: based on tool outcome + message content

### C4: Semantic Memory Search ✅ DONE
- Built-in TF-IDF (`semantic_memory.py`)
- Documents get indexed, refactored from keywords to embeddings later
- Cross-session fact lookup

### C5: Error Auto-Heal ✅ DONE
- When tool fails twice, self-healer regenerates with corrected approach
- `should_error_heal()` logic checks disallowed paths, tries fallback

### C6: Learning Graph Integration ✅ DONE
- Tracks tool success rates per message history
- Improves tool selection over time
- `/doctor` shows learning-graph insights

### C7: Custom Agent Creation ✅ DONE
- `/agent` slash command: list/create/edit custom agents
- Agents = `.openforge/agents/*.json` with per-agent system prompt + tool restrictions
- Used by  `.openforge/agent-slug/` for persistent settings

## 🎯 Phase D: Installer Upgraded Experience

### D1: Improved Install Scripts ✅ DONE
- Spinner animations during long tasks
- Percentage progress bars
- Unicode logos + sparkly frames
- Welcome banner with forge artwork
- Auto-detection of system tools

### D2: First-Time Setup Wizard
- After install, prompt: "Choose your first provider"
  - (tokenrouter, openai, ollama, llama.cpp, lmstudio, vllm, databricks, Web LLM)
- Prompt: "Set your API key for X" (secure hidden input)
- Prompt: "Preferred model name?" (sensible default)
- Auto-installs dependency deps for chosen provider
- Writes to `~/.openforge/providers.json` (masked storage)

## 🎯 Phase E: Router between Tools + TUI

### E1: Add Smart Tool Router
- Classify user input: (read file / write file / search web / run code / execute cmd / delegate / research)
- Route to best tool with sensible fallbacks
- Handles edge cases (e.g. "search for X" → web_search → deep_search if needs more depth)
- Use IntentClassifier module (v2.0) + confidence scoring

### E2: TUI Improvements ✅ DONE (v2.1.0)
- Multi-pane layout (status bar + chat + tool log)
- Tool-call visualization with icons + timing
- Streaming response preview
- Slash command dispatch
- Provider model switching

## 🚀 Phase F: Release v3.0.0 (FINAL)

### Tasks:
- [ ] Add xterm.js PTY to TerminalPanel
- [ ] Complete Sandbox UI (preview + terminal split)
- [ ] Add 4 Quick Action chips to Composer
- [ ] Add session rename UI (inline edit)
- [ ] Add tool chip integration after tool calls
- [ ] Test with Ornith E2E
- [ ] Fix any remaining console errors
- [ ] Package as `.zip` one-install bundle
- [ ] Write GitHub Release notes
- [ ] Bump version to v3.1.0 → tag → push → release

---

## ✅ Status V3 Launch Versions

| Version | Focus                             | Test Count | Notes |
|---------|-----------------------------------|------------|-------|
| v3.0.0 | Bug fixes + UI Polish            | 480 pass   | Working良好的基础 ✅ |
| v3.1.0 | Web UI est + Terminal + Sandbox   | 552 pass   | Big UX upgrade |
| v3.2.0 | Installer final polish + DeepSearch | ?    | Ongoing |