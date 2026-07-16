/**
 * Nexa Agent — Memory System
 *
 * Persistent, cross-session memory store backed by the database. The agent
 * can save notes, facts and preferences, then recall them later. This is the
 * web equivalent of the ~/.nexa/memory/MEMORY.md file in the CLI build.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { db } from "@/lib/db";
import type { NexaMemory } from "./types";

export const MEMORY_KINDS = ["note", "fact", "preference", "skill"] as const;
export type MemoryKind = (typeof MEMORY_KINDS)[number];

/** Serialize active memory into a markdown digest for the system prompt. */
export async function renderMemoryDigest(limit = 24): Promise<string> {
  const items = await db.nexaMemory.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
  });
  if (items.length === 0) {
    return "(no memories stored yet)";
  }
  return items
    .map((m) => `- [${m.kind}] ${m.content}`)
    .join("\n");
}

/** Save a new memory record. */
export async function saveMemory(
  kind: MemoryKind,
  content: string
): Promise<NexaMemory> {
  const created = await db.nexaMemory.create({
    data: { kind, content: content.trim() },
  });
  return toMemory(created);
}

/** Recall memories matching a free-text query (simple substring + recency). */
export async function recallMemory(query: string, limit = 8): Promise<NexaMemory[]> {
  const q = query.trim().toLowerCase();
  const all = await db.nexaMemory.findMany({
    orderBy: { createdAt: "desc" },
    take: 100,
  });
  const filtered = q
    ? all.filter((m) => m.content.toLowerCase().includes(q))
    : all;
  return filtered.slice(0, limit).map(toMemory);
}

/** List all memories, newest first. */
export async function listMemory(limit = 100): Promise<NexaMemory[]> {
  const items = await db.nexaMemory.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
  });
  return items.map(toMemory);
}

/** Delete a memory by id. */
export async function deleteMemory(id: string): Promise<boolean> {
  try {
    await db.nexaMemory.delete({ where: { id } });
    return true;
  } catch {
    return false;
  }
}

function toMemory(row: {
  id: string;
  kind: string;
  content: string;
  createdAt: Date;
}): NexaMemory {
  return {
    id: row.id,
    kind: row.kind as NexaMemory["kind"],
    content: row.content,
    createdAt: row.createdAt.toISOString(),
  };
}
