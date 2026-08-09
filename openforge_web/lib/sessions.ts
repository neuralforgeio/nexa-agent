/**
 * OpenForge — Session list helpers (F-03 search + F-04 pin/archive/grouping)
 *
 * Pure functions, easy to unit-test in isolation. The UI components
 * (Sidebar.tsx) call into these to keep render logic thin.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { Session } from "./theme";

export type SessionGroup = "Today" | "Yesterday" | "Older";

/**
 * Bucket an ISO timestamp into a relative-day group. Invalid dates fall
 * into "Older" so the UI never crashes on bad input.
 */
export function groupLabel(iso: string): SessionGroup {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Older";
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const thatMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((midnight.getTime() - thatMidnight.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return "Older";
}

/**
 * Case-insensitive substring filter over title (and tolerant of backends
 * that may include a snippet field in the future).
 */
export function filterSessions(sessions: Session[], query: string): Session[] {
  const q = query.trim().toLowerCase();
  if (!q) return sessions;
  return sessions.filter((s) => {
    const title = (s.title ?? "").toLowerCase();
    if (title.includes(q)) return true;
    const maybeSnippet = (s as Session & { snippet?: string }).snippet;
    if (typeof maybeSnippet === "string" && maybeSnippet.toLowerCase().includes(q)) return true;
    return false;
  });
}

/**
 * Split a list of sessions into pinned / normal (visible) / archived,
 * preserving input order inside each bucket.
 */
export function splitByPinArchive(sessions: Session[]): {
  pinned: Session[];
  normal: Session[];
  archived: Session[];
} {
  const pinned: Session[] = [];
  const normal: Session[] = [];
  const archived: Session[] = [];
  for (const s of sessions) {
    if (s.archived) archived.push(s);
    else if (s.pinned) pinned.push(s);
    else normal.push(s);
  }
  return { pinned, normal, archived };
}

/**
 * Group an array of sessions by Today/Yesterday/Older, preserving input
 * order within each bucket.
 */
export function groupByDate(sessions: Session[]): Record<SessionGroup, Session[]> {
  const buckets: Record<SessionGroup, Session[]> = {
    Today: [],
    Yesterday: [],
    Older: [],
  };
  for (const s of sessions) {
    buckets[groupLabel(s.updatedAt)].push(s);
  }
  return buckets;
}

/**
 * PATCH the pinned/archived flags for a session. Uses optimistic caller;
 * this helper simply performs the network request and reports success.
 */
export async function patchSessionFlags(
  id: string,
  patch: { pinned?: boolean; archived?: boolean; title?: string }
): Promise<boolean> {
  try {
    const res = await fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Create a new branch of the conversation starting from a given message.
 * Returns the new session id, or null on failure.
 */
export async function branchSession(payload: {
  sessionId: string | null;
  messageId: string;
}): Promise<string | null> {
  try {
    const res = await fetch("/api/sessions/branch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { id?: string; sessionId?: string };
    return data.id ?? data.sessionId ?? null;
  } catch {
    return null;
  }
}
