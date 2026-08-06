# F-02 Message Actions — Plan (Direct-to-main, v4.6.5 → then tag v4.6.5)

## Goal
Give every message in `nexa_web/components/MessageBubble.tsx` a hover toolbar with four actions:
- Copy: `navigator.clipboard.writeText(message.content)`
- Regenerate (assistant messages only): re-send the preceding user prompt through `onSend`
- Edit & Resubmit (user messages only): inline textarea pre-filled with the message content; submitting calls `onSend(newText)`
- Branch: POST `/api/sessions/branch` with `{ sessionId, messageId }` and navigate to the new branch

## Why
Spec Category-1 F-02. Currently MessageBubble is render-only; users have no way to act on turns.

## Files touched
1. `nexa_web/components/MessageBubble.tsx` — add toolbar UI + `actions` prop (optional callbacks). Local state: `hovered`, `copyOk`, `editing`, `editDraft`, `branching`.
2. `nexa_web/app/page.tsx` — map messages with index and message.id, wire callbacks: `onCopy` native in bubble; `onRegenerate(idx)` → find nearest preceding user message → `onSend`; `onEditSubmit(idx, text)` → `onSend(text)`; `onBranch(idx)` → POST branch → setSessionId(new).
3. `nexa_web/lib/sessions.ts` — already has `branchSession`; reuse it.
4. `nexa_web/tests/message-actions.test.tsx` — 3 tests.

## Impact
- Backward compatible: actions prop optional, existing render unchanged when omitted.
- No backend change needed for F-02 minimal: branch endpoint already claimed in sessions.ts helpers — need to verify backend supports `POST /api/sessions/branch`; if missing, add alias in server.py (deferred to F-02 backend if needed).

## Backend check
- `grep "sessions/branch" src/server.py` → if missing, add small endpoint:
  - GET source session messages up to (and including) messageId; create new session; insert copies; return new id. (new DB helper `branch_conversation(from_id, up_to_message_id)` in nexa/state.py)

## Tests (3 required)
1. toolbar appears on hover, has 4 buttons for assistant / subset (copy|edit|branch) for user.
2. copy button → navigator.clipboard mock called with content, shows copied state, recovers.
3. regenerate → calls onRegenerate → parent onSend fired with original prompt text.
4. edit-submit → inline edit replaces content and calls onEditSubmit.
5. branch → POST called, parent navigates to returned id.

At least the 3 core scenarios above guaranteed; extra cases if trivial.

## QA
npm run lint (0 err), npm test (new tests + regression), npm run build OK, pytest full no new fails, version sync 4.6.5 in 3 files, doctor healthy.

## Bump plan
PATCH 4.6.4 → 4.6.5 (feature-in-scope-of-patch per user: per-tool patch bumps, MINOR at category close).
