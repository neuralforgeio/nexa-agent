/**
 * Nexa Agent — Streaming Chat API (SSE)
 *
 * POST /api/chat/stream
 * Body: { message: string, history?: NexaMessage[] }
 *
 * Pure streaming — NO database writes. The caller is responsible for
 * persisting the result via POST /api/chat/persist after the stream ends.
 *
 * Events:
 *   data: {"type":"thinking"}
 *   data: {"type":"token","text":"..."}
 *   data: {"type":"tool_call","toolRequest":{...}}
 *   data: {"type":"tool_result","toolResult":{...}}
 *   data: {"type":"done","answer":"...","iterations":N}
 *   data: {"type":"error","message":"..."}
 *   data: {"type":"end"}
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NextRequest } from "next/server";
import { NexaAgent } from "@/lib/nexa/agent";
import type { NexaMessage } from "@/lib/nexa/types";

let agentPromise: Promise<NexaAgent> | null = null;
async function getAgent(): Promise<NexaAgent> {
  if (!agentPromise) agentPromise = Promise.resolve(new NexaAgent());
  return agentPromise;
}

export async function POST(req: NextRequest) {
  let body: { message?: string; history?: NexaMessage[] };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const message = (body.message ?? "").trim();
  if (!message) {
    return new Response(JSON.stringify({ error: "message is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const agent = await getAgent();
  const history = body.history ?? [];

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: unknown) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      };

      try {
        for await (const event of agent.runStreaming(message, history)) {
          send(event);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        send({ type: "error", message: msg });
      } finally {
        send({ type: "end" });
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
