/**
 * Nexa Agent — SSE Stream Parser
 *
 * Parses Server-Sent Events from the Python agent backend.
 * Handles all event types: session, thinking, token, tool_call,
 * tool_result, done, error, end, compressing, memory.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { ChatEvent } from "./theme";

/**
 * Parse an SSE stream from the agent backend.
 *
 * @param reader - ReadableStream reader from fetch()
 * @param onEvent - Callback for each parsed event
 * @returns Promise that resolves when stream ends
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (event: ChatEvent) => void
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      const json = line.slice(6);
      try {
        const event: ChatEvent = JSON.parse(json);
        onEvent(event);
      } catch {
        // Skip malformed events
      }
    }
  }
}

/**
 * Send a chat message via SSE streaming.
 *
 * @param message - User message
 * @param sessionId - Optional session ID
 * @param onEvent - Callback for each event
 * @returns The session ID from the response
 */
export async function sendChatMessage(
  message: string,
  sessionId: string | null,
  onEvent: (event: ChatEvent) => void
): Promise<string | null> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, sessionId }),
  });

  if (!res.ok || !res.body) {
    const errText = await res.text().catch(() => "request failed");
    onEvent({ type: "error", message: errText });
    return null;
  }

  let boundSessionId: string | null = null;
  const reader = res.body.getReader();

  await parseSSEStream(reader, (event) => {
    if (event.type === "session" && event.sessionId) {
      boundSessionId = event.sessionId;
    }
    onEvent(event);
  });

  return boundSessionId;
}

/**
 * Persist a completed chat turn.
 *
 * @param sessionId - Session ID
 * @param userMessage - User's message
 * @param assistantAnswer - Agent's answer
 * @param toolResults - Tool results from the turn
 */
export async function persistTurn(
  sessionId: string,
  userMessage: string,
  assistantAnswer: string,
  toolResults: Array<{ tool: string; output: string }>
): Promise<void> {
  try {
    await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "persist",
        sessionId,
        userMessage,
        assistantAnswer,
        toolResults,
      }),
    });
  } catch {
    // Persistence failure is non-fatal
  }
}
