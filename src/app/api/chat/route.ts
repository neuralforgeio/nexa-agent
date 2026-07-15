/**
 * Nexa Agent — Chat API
 *
 * POST /api/chat
 * Body: { sessionId?: string, message: string }
 * Runs one agent turn (with tool calling) and persists the transcript.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { NexaAgent } from "@/lib/nexa/agent";
import type { NexaMessage } from "@/lib/nexa/types";

// A single long-lived agent instance per server process.
let agentPromise: Promise<NexaAgent> | null = null;
async function getAgent(): Promise<NexaAgent> {
  if (!agentPromise) {
    agentPromise = Promise.resolve(new NexaAgent());
  }
  return agentPromise;
}

function deriveTitle(message: string): string {
  const clean = message.replace(/\s+/g, " ").trim();
  if (clean.length <= 48) return clean || "new session";
  return clean.slice(0, 48).trimEnd() + "…";
}

function rowToMessage(row: {
  id: string;
  role: string;
  content: string;
  toolName: string | null;
  toolCallId: string | null;
  createdAt: Date;
}): NexaMessage {
  return {
    id: row.id,
    role: row.role as NexaMessage["role"],
    content: row.content,
    toolName: row.toolName ?? undefined,
    toolCallId: row.toolCallId ?? undefined,
    createdAt: row.createdAt.toISOString(),
  };
}

export async function POST(req: NextRequest) {
  let body: { sessionId?: string; message?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const message = (body.message ?? "").trim();
  if (!message) {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  const agent = await getAgent();

  // Resolve or create the session.
  let sessionId = body.sessionId;
  let isNew = false;
  if (!sessionId) {
    const created = await db.nexaSession.create({
      data: { title: deriveTitle(message) },
    });
    sessionId = created.id;
    isNew = true;
  } else {
    const exists = await db.nexaSession.findUnique({ where: { id: sessionId } });
    if (!exists) {
      return NextResponse.json({ error: "session not found" }, { status: 404 });
    }
  }

  // Load history (exclude system rows).
  const rows = await db.nexaMessage.findMany({
    where: { sessionId },
    orderBy: { createdAt: "asc" },
  });
  const history: NexaMessage[] = rows
    .filter((r) => r.role !== "system")
    .map(rowToMessage);

  // Persist the user message first.
  await db.nexaMessage.create({
    data: { sessionId, role: "user", content: message },
  });

  // Run the agent turn.
  let result;
  try {
    result = await agent.runConversation(message, history);
  } catch (err) {
    const text = err instanceof Error ? err.message : String(err);
    await db.nexaMessage.create({
      data: {
        sessionId,
        role: "assistant",
        content: `[Nexa] agent error: ${text}`,
      },
    });
    await db.nexaSession.update({
      where: { id: sessionId },
      data: { updatedAt: new Date() },
    });
    return NextResponse.json(
      { error: "agent failure", detail: text, sessionId },
      { status: 500 }
    );
  }

  // Persist intermediate tool results, then the final answer.
  for (const step of result.steps) {
    if (step.kind === "tool_result" && step.toolResult) {
      await db.nexaMessage.create({
        data: {
          sessionId,
          role: "tool",
          content: step.toolResult.output,
          toolName: step.toolResult.tool,
        },
      });
    }
  }
  await db.nexaMessage.create({
    data: { sessionId, role: "assistant", content: result.answer },
  });
  await db.nexaSession.update({
    where: { id: sessionId },
    data: { updatedAt: new Date() },
  });

  return NextResponse.json({
    sessionId,
    isNew,
    answer: result.answer,
    steps: result.steps,
    iterations: result.iterations,
  });
}
