/**
 * Nexa Agent — Export API
 *
 * GET /api/export/:id  — download a session transcript as a Markdown file.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { NEXA_AUTHOR, NEXA_NAME, NEXA_VERSION } from "@/lib/nexa/constants";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const session = await db.nexaSession.findUnique({
    where: { id },
    include: { messages: { orderBy: { createdAt: "asc" } } },
  });
  if (!session) {
    return NextResponse.json({ error: "session not found" }, { status: 404 });
  }

  const lines: string[] = [];
  lines.push(`# ${session.title}`);
  lines.push("");
  lines.push(
    `> Exported from ${NEXA_NAME} v${NEXA_VERSION} · © 2026 ${NEXA_AUTHOR}`
  );
  lines.push(`> Session ID: \`${session.id}\``);
  lines.push(
    `> Created: ${session.createdAt.toISOString()} · Updated: ${session.updatedAt.toISOString()}`
  );
  lines.push("");
  lines.push("---");
  lines.push("");

  for (const m of session.messages) {
    const ts = m.createdAt.toISOString();
    if (m.role === "user") {
      lines.push(`### 🧑 User`);
      lines.push("");
      lines.push(m.content);
      lines.push("");
    } else if (m.role === "assistant") {
      lines.push(`### ⚡ Nexa Agent`);
      lines.push("");
      lines.push(m.content);
      lines.push("");
    } else if (m.role === "tool") {
      lines.push(`<details>`);
      lines.push(`<summary>🔧 Tool: ${m.toolName ?? "unknown"} (${ts})</summary>`);
      lines.push("");
      lines.push("```");
      lines.push(m.content);
      lines.push("```");
      lines.push("");
      lines.push(`</details>`);
      lines.push("");
    }
  }

  const md = lines.join("\n");
  const safeTitle = session.title.replace(/[^a-z0-9-_ ]/gi, "").slice(0, 40).trim() || "nexa-session";
  const filename = `${safeTitle.replace(/\s+/g, "-").toLowerCase()}.md`;

  return new NextResponse(md, {
    status: 200,
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
