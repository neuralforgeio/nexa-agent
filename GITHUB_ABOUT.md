# GitHub Repository "About" Settings — v4.1.0

The commands below populate the GitHub **About** panel for
`neuralforgeio/nexa-agent`. They require the [`gh`](https://cli.github.com/) CLI
(authenticated via `gh auth login`) or a `GITHUB_TOKEN` env var with
`repo` scope.

## 1. Install + authenticate the GitHub CLI

```powershell
winget install GitHub.cli
gh auth login                    # choose github.com / HTTPS / browser
gh auth status                   # should show "Logged in to github.com"
```

## 2. Set the repository description + homepage

```powershell
gh repo edit neuralforgeio/nexa-agent `
  --description "Local-first AI agent — Security-hardened (v4.1.0), virtual multi-agent orchestrator (Planner→Explorer→Coder→Reviewer FSM), 30+ tools, FTS5 memory, SSE streaming to a Next.js 16 web UI, local LLM & 8-provider ready (llama.cpp / Ollama / OpenAI / Anthropic / TokenRouter / Databricks)." `
  --homepage "https://github.com/neuralforgeio/nexa-agent"
```

## 3. Add the topics

```powershell
gh repo edit neuralforgeio/nexa-agent `
  --add-topic "ai" `
  --add-topic "ai-agent" `
  --add-topic "local-llm" `
  --add-topic "llama-cpp" `
  --add-topic "ollama" `
  --add-topic "openai-compatible" `
  --add-topic "multi-agent" `
  --add-topic "state-machine" `
  --add-topic "tool-calling" `
  --add-topic "memory" `
  --add-topic "fts5" `
  --add-topic "fastapi" `
  --add-topic "nextjs-16" `
  --add-topic "sse-streaming" `
  --add-topic "windows-pty" `
  --add-topic "security-hardened" `
  --add-topic "python-3-12" `
  --add-topic "typescript" `
  --add-topic "self-hosted"
```

## 4. Disable wiki / projects / discussions if you don't use them

```powershell
gh repo edit neuralforgeio/nexa-agent --enable-wiki=false
gh repo edit neuralforgeio/nexa-agent --enable-projects=false
gh repo edit neuralforgeio/nexa-agent --enable-discussions=false
```

## 5. Create the GitHub Release for v4.1.0

```powershell
gh release create v4.1.0 --title "Nexa Agent v4.1.0 — Security Hardening + Virtual Multi-Agent + 8 Bug Fixes" --notes-file RELEASE_NOTES_v4.1.0.md
```

(`RELEASE_NOTES_v4.1.0.md` is the content of the v4.1.0 commit message I
prepared; it's also in `.plans/release_body.json`.)

## 6. Verify

```powershell
gh repo view neuralforgeio/nexa-agent
```

You should see the new description, homepage, and topics at the top of
https://github.com/neuralforgeio/nexa-agent.

---

> If you prefer to stay in the browser instead:
> 1. Open https://github.com/neuralforgeio/nexa-agent.
> 2. Click the ⚙️ **gear icon** in the top-right of the About panel.
> 3. Paste the description above into **Description**.
> 4. Paste `https://github.com/neuralforgeio/nexa-agent` into **Website**.
> 5. In **Topics**, type each topic above and press <kbd>Enter</kbd> after each.
> 6. Click **Save changes**.
EOF
