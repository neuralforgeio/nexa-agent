/**
 * Nexa Agent — Notes API
 *
 * GET    /api/notes?sessionId=...   — list notes for a session
 * POST   /api/notes                 — create a note { sessionId, content, pinned? }
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { createNote, listNotes } from "@/lib/nexa/notes";

export async function GET(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("sessionId");
  if (!sessionId) {
    return NextResponse.json(
      { error: "sessionId is required" },
      { status: 400 }
    );
  }
  const notes = await listNotes(sessionId);
  return NextResponse.json({ notes });
}

export async function POST(req: NextRequest) {
  let body: { sessionId?: string; content?: string; pinned?: boolean } = {};
  try {
    body = await req.json();
  } catch {
    /* ignore */
  }
  const sessionId = body.sessionId;
  const content = (body.content ?? "").trim();
  if (!sessionId) {
    return NextResponse.json({ error: "sessionId is required" }, { status: 400 });
  }
  if (!content) {
    return NextResponse.json({ error: "content is required" }, { status: 400 });
  }
  const note = await createNote(sessionId, content, body.pinned ?? false);
  return NextResponse.json({ note });
}
