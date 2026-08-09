# OpenForge — Web UI (Frontend)

Next.js 16 + React 19 + Tailwind v4 frontend for Nexa Agent. Dark mode
`#141618` (Z.ai-style), pill-shaped composer, sidebar with session
history, SSE streaming with auto-reconnect.

## Quick Start

```bash
# 1. Install dependencies
cd nexa_web
npm install

# 2. Start the Python backend (must be running on port 8000)
cd ..
.venv/Scripts/python.exe server.py

# 3. Start the dev server (port 3000)
cd nexa_web
npm run dev
```

Open http://localhost:3000 in your browser.

## Architecture

```
nexa_web/
├── app/
│   ├── globals.css         # Tailwind v4 import + scrollbar styles
│   ├── layout.tsx          # Root layout (dark theme, system fonts)
│   └── page.tsx             # Main chat page (state, SSE, empty state)
├── components/
│   ├── Composer.tsx        # Pill-shaped input + suggestion chips
│   ├── MessageBubble.tsx    # User/assistant message rendering
│   ├── Sidebar.tsx          # Session history + New chat
│   └── ThinkingIndicator.tsx # Streaming cursor + collapsible tool cards
├── lib/
│   ├── stream.ts           # SSE parser + reconnect logic
│   └── theme.ts            # Design tokens + types + formatters
├── public/
│   └── nexa-agent.png      # Logo (copied from repo root)
├── next.config.ts          # /api/* → http://127.0.0.1:8000/api/* proxy
├── tsconfig.json           # Strict mode (v2.1.0)
├── package.json            # v2.1.0
└── postcss.config.mjs      # Tailwind v4 PostCSS plugin
```

## API Proxy

All `/api/*` requests are proxied to the Python backend at
`http://127.0.0.1:8000/api/*` via `next.config.ts` rewrites. The browser
only ever talks to port 3000.

## v2.1.0 Hardening

- **Strict TypeScript**: `tsconfig.json` `strict: true`, `ignoreBuildErrors: false`.
- **No dead deps**: removed `z-ai-web-dev-sdk` (unused), `clsx`, `tailwind-merge`.
- **Cross-platform scripts**: `dev`/`build`/`start` use plain `next` commands (no Unix-only `cp`/`tee`).
- **Mobile sidebar**: hamburger toggle (was hardcoded `display:none`).
- **SSE reconnect**: exponential backoff (1s→2s→4s→8s, max 4 attempts) with `onStatus` callback for "Connection lost. Reconnecting…" banners.
- **Typed shapes**: replaced `any` casts with typed `SessionMessage` interface.
- **Version sync**: empty state reads version from `/api/health` (no more hardcoded "v1.8.0").
- **Logo asset**: `nexa-agent.png` copied into `nexa_web/public/` (was 404).

## Known Issue: Next.js 16 + Turbopack on Windows

`npm run build` may fail on Windows with:
```
The "id" argument must be of type string. Received undefined
Next.js build worker exited with code: 1 and signal: null
```

This is a **known Turbopack bug on Windows** (Next.js 16.2.10), not a code
defect. `npx tsc --noEmit` passes with 0 errors, and the build compiles
successfully (`✓ Compiled successfully`) before the worker crashes.

**Workarounds**:
- Use `npm run dev` for development (Turbopack dev mode works fine).
- On Linux/macOS, `npm run build` succeeds.
- On Windows, downgrade to Next.js 15 (requires `next.config.js` instead of `.ts`) until the Turbopack bug is fixed.

## Scripts

- `npm run dev` — Start dev server on port 3000 (with Turbopack).
- `npm run build` — Production build (may fail on Windows due to Turbopack bug; see above).
- `npm run start` — Start production server on port 3000.
- `npm run lint` — Run ESLint.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
