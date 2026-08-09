# OpenForge — Discussions Welcome Template
# ----------------------------------------
# How to use: paste the text below as the opening comment in the relevant
# Discussion category. Adapt the bracketed sections.

<!--
Available categories (GitHub default):
- Announcements
- General
- Ideas
- Q&A
- Show and tell
-->

## About OpenForge

**OpenForge** is the continuation of `openforge` — a local-first AI agent with:
- 43 built-in tools
- 44 skills across 6 categories
- 41 intelligence modules (self-healing, self-improvement, confidence scoring, …)
- 25 LLM providers (+ custom endpoints)
- Unified home: `~/.openforge/`

## Migration from `openforge`

If you forked `neuralforgeio/openforge`:
- The repository has been **renamed** to `neuralforgeio/openforge`.  
  GitHub auto-redirects old URLs, so existing clone URLs keep working.
- Environment variables `FORGE_*` are becoming `FORGE_*`. The old names still
  resolve via a compatibility shim for one MINOR cycle.
- Set-open up pulls from the new default branch `main` as usual.

Run:
```bash
openforge doctor
openforge migrate        # Phase 3 — moves ~/.openforge → ~/.openforge with backup
openforge --version      # → OpenForge v5.x.x
```
