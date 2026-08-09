# Research: Autonomous Agent Development Loop (NADL)

## Summary
The "NADL" (OpenForge Development Loop) is the on-going autonomy cadence:
an agent that periodically reviews its own state, plans improvements (or
fixes), executes them with test gates, and reports metrics. The goal is
to eliminate rote work without turning the agent into a runaway
self-modifier.

## Findings

### Devin / Cognition (concept)
- **Approach:** Treat each user task as a long-running plan. Use a
  document-store for artifacts, a sandbox for execution, and an LLM
  that can call into shell/editor/browser tools.
- **Pros:** Users can delegate multi-hour work; planner/executor events
  are first-class, so progress is observable.
- **Cons:** OpenAI-style plans tend to drift; long autonomy requires a
  strong "safety budget" (cost, time, side-effects). A second
  opinion/reviewer agent becomes necessary.
- **Applied to openforge:** The existing orchestrator already models
  phase transitions; the Planner/Coder/Reviewer roles align well with
  this pattern.

### OpenHands / OpenDevin
- **Approach:** Containerized sandbox (Docker), event stream for the UI,
  per-turn affordances (run command / browse / edit / answer).
- **Pros:** Strong isolation; bundled web server; flexible messaging.
- **Cons:** Heavyweight; not local-first. Requires infrastructure.
- **Applied to openforge:** The virtual-agent states map neatly onto
  OpenHands's flow state, but we keep local execution (llama.cpp,
  Ornith) as first-class.

### Modular Hermes / ZCode-style continuous loop
- **Approach:** Cron-driven ticks: review, plan, execute, test, commit.
  The current ZCode skill set (SessionContext, TodoWrite, Agent-tools)
  implements this directly.
- **Pros:** Fits into existing tooling; small footprint.
- **Cons:** Cadence is bounded by developer availability unless the
  agent runs autonomously at scale — which we deliberately do not do.

## Benchmark Comparison

| Tool | Autonomy | Sandboxing | Local-first | Memory | Tool API | Cost |
|------|----------|------------|-------------|--------|----------|------|
| Devin | High | Container | No | Session | Rich | $$$ SaaS |
| OpenHands | High | Docker | Partial | Session | Medium | $$ Cloud |
| ZCode (current) | Medium | Per-tool allowlist | Yes | Persistent | Tool API | Free |
| openforge today | Medium-High | Workspace sandbox | Yes | Persistent | Built-in | Free |

## Recommendations

1. Keep the existing `Orchestrator` + `PersonaManager` as the basis.
   Do not rewrite.
2. Layer an iterative QA-and-fix cadence on top, but always in a
   separate, fully-tested demo branch before merging into `main`.
3. Document the loop design in a single place (this file) and commit
   to it (no forking).

## Open Questions
- Should Forge expose a "long-running autonomous mode" toggle that
  disables human-in-the-loop prompts?
- Should the v4.3 work be conservative (smaller features spread across
  versions) or move to a unified v5.0 board with bigger alternatives?
