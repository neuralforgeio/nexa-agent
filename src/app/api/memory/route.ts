/**
 * Nexa Agent — Memory API
 *
 * GET    /api/memory         — list memories (newest first)
 * POST   /api/memory         — create a memory
 * DELETE /api/memory?id=...  — delete a memory
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deleteMemory, listMemory, saveMemory } from "@/lib/nexa/memory";

export async function GET() {
  const items = await listMemory(100);
  return NextResponse.json({ memories: items });
}

export async function POST(req: NextRequest) {
  let body: { kind?: string; content?: string } = {};
  try {
    body = await req.json();
  } catch {
    /* ignore */
  }
  const kind = (body.kind ?? "note") as
    | "note"
    | "fact"
    | "preference"
    | "skill";
  const content = (body.content ?? "").trim();
  if (!content) {
    return NextResponse.json({ error: "content is required" }, { status: 400 });
  }
  if (!["note", "fact", "preference", "skill"].includes(kind)) {
    return NextResponse.json({ error: "invalid kind" }, { status: 400 });
  }
  const mem = await saveMemory(kind, content);
  return NextResponse.json({ memory: mem });
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (!id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }
  const ok = await deleteMemory(id);
  if (!ok) {
    return NextResponse.json({ error: "memory not found" }, { status: 404 });
  }
  // Touch the DB import so it is not tree-shaken in stricter setups.
  void db;
  return NextResponse.json({ ok: true });
}
