/**
 * Nexa Agent — Note item API
 *
 * PATCH   /api/notes/:id  — toggle pin { pinned?: boolean }
 * DELETE  /api/notes/:id  — delete a note
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { deleteNote, togglePinNote } from "@/lib/nexa/notes";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  let body: { pinned?: boolean } = {};
  try {
    body = await req.json();
  } catch {
    /* ignore */
  }
  if (typeof body.pinned === "boolean") {
    try {
      await db.nexaNote.update({ where: { id }, data: { pinned: body.pinned } });
      return NextResponse.json({ ok: true });
    } catch {
      return NextResponse.json({ error: "note not found" }, { status: 404 });
    }
  }
  // default: toggle
  const ok = await togglePinNote(id);
  if (!ok) {
    return NextResponse.json({ error: "note not found" }, { status: 404 });
  }
  return NextResponse.json({ ok: true });
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const ok = await deleteNote(id);
  if (!ok) {
    return NextResponse.json({ error: "note not found" }, { status: 404 });
  }
  return NextResponse.json({ ok: true });
}
