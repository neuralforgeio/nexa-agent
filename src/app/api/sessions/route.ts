/**
 * Nexa Agent — Sessions API
 *
 * GET  /api/sessions        — list sessions (newest first)
 * POST /api/sessions        — create a new (empty) session
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET() {
  const sessions = await db.nexaSession.findMany({
    orderBy: { updatedAt: "desc" },
    take: 100,
    select: {
      id: true,
      title: true,
      createdAt: true,
      updatedAt: true,
      _count: { select: { messages: true } },
    },
  });
  return NextResponse.json({
    sessions: sessions.map((s) => ({
      id: s.id,
      title: s.title,
      createdAt: s.createdAt.toISOString(),
      updatedAt: s.updatedAt.toISOString(),
      messageCount: s._count.messages,
    })),
  });
}

export async function POST(req: NextRequest) {
  let body: { title?: string } = {};
  try {
    body = await req.json();
  } catch {
    /* empty body is fine */
  }
  const title = (body.title ?? "new session").trim() || "new session";
  const created = await db.nexaSession.create({ data: { title } });
  return NextResponse.json({
    session: {
      id: created.id,
      title: created.title,
      createdAt: created.createdAt.toISOString(),
      updatedAt: created.updatedAt.toISOString(),
      messageCount: 0,
    },
  });
}
