/**
 * Nexa Agent — Session Notes (Scratchpad)
 *
 * Per-session working notes the agent can jot down during complex multi-step
 * tasks. Unlike long-term memory, notes are scoped to a single session and
 * are deleted with it. Users can pin important notes to keep them on top.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { db } from "@/lib/db";

export interface NexaNoteItem {
  id: string;
  sessionId: string;
  content: string;
  pinned: boolean;
  createdAt: string;
}

/** List notes for a session (pinned first, then newest). */
export async function listNotes(sessionId: string): Promise<NexaNoteItem[]> {
  const rows = await db.nexaNote.findMany({
    where: { sessionId },
    orderBy: [{ pinned: "desc" }, { createdAt: "desc" }],
  });
  return rows.map(toNote);
}

/** Create a new note in a session. */
export async function createNote(
  sessionId: string,
  content: string,
  pinned = false
): Promise<NexaNoteItem> {
  const row = await db.nexaNote.create({
    data: { sessionId, content: content.trim(), pinned },
  });
  return toNote(row);
}

/** Toggle a note's pinned state. */
export async function togglePinNote(id: string): Promise<boolean> {
  const existing = await db.nexaNote.findUnique({ where: { id } });
  if (!existing) return false;
  await db.nexaNote.update({
    where: { id },
    data: { pinned: !existing.pinned },
  });
  return true;
}

/** Delete a note by id. */
export async function deleteNote(id: string): Promise<boolean> {
  try {
    await db.nexaNote.delete({ where: { id } });
    return true;
  } catch {
    return false;
  }
}

/** Clear all non-pinned notes in a session. */
export async function clearNotes(sessionId: string): Promise<number> {
  const result = await db.nexaNote.deleteMany({
    where: { sessionId, pinned: false },
  });
  return result.count;
}

function toNote(row: {
  id: string;
  sessionId: string;
  content: string;
  pinned: boolean;
  createdAt: Date;
}): NexaNoteItem {
  return {
    id: row.id,
    sessionId: row.sessionId,
    content: row.content,
    pinned: row.pinned,
    createdAt: row.createdAt.toISOString(),
  };
}
