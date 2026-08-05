/**
 * Nexa Agent — SSE Stream Parser (Hardened v2.1.0)
 *
 * Parses Server-Sent Events from the Python agent backend.
 * Handles all event types: session, thinking, token, tool_call,
 * tool_result, done, error, end, compressing, memory.
 *
 * v2.1.0 additions:
 * - Exponential-backoff reconnect on dropped connections (1s→2s→4s→8s).
 * - Connection-status callback (`onStatus`) so the UI can surface a
 *   "Connection lost. Reconnecting…" banner.
 * - No more forever-blinking cursor: if reconnect gives up, an `error`
 *   event is emitted so the UI clears the thinking state.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { ChatEvent } from "./theme";

export type ConnectionStatus = "connected" | "reconnecting" | "lost" | "idle";

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000];

/**
 * Parse an SSE stream from the agent backend.
 *
 * @param reader - ReadableStream reader from fetch()
 * @param onEvent - Callback for each parsed event
 * @returns Promise that resolves when the stream ends cleanly.
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
        const event = JSON.parse(json) as ChatEvent;
        onEvent(event);
      } catch {
        // Skip malformed events.
      }
    }
  }
}

/**
 * Send a chat message via SSE streaming, with reconnect on dropped connections.
 *
 * @param message - User message.
 * @param sessionId - Optional session ID.
 * @param onEvent - Callback for each parsed event.
 * @param onStatus - Optional connection-status callback (for UI banners).
 * @param signal - Optional AbortSignal (F-01 stop button aborts the stream).
 * @returns The session ID bound during the stream, or null on failure.
 */
export async function sendChatMessage(
  message: string,
  sessionId: string | null,
  onEvent: (event: ChatEvent) => void,
  onStatus?: (status: ConnectionStatus) => void,
  signal?: AbortSignal
): Promise<string | null> {
  let boundSessionId: string | null = null;
  const isAborted = () => signal?.aborted === true;

  for (let attempt = 0; attempt <= RECONNECT_DELAYS_MS.length; attempt++) {
    if (isAborted()) {
      onStatus?.("idle");
      return boundSessionId;
    }
    try {
      onStatus?.(attempt === 0 ? "connected" : "reconnecting");
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, sessionId }),
        signal,
      });

      if (!res.ok || !res.body) {
        const errText = await res.text().catch(() => "request failed");
        // Non-retryable HTTP error.
        onStatus?.("lost");
        onEvent({ type: "error", message: errText });
        return null;
      }

      const reader = res.body.getReader();
      await parseSSEStream(reader, (event) => {
        if (event.type === "session" && event.sessionId) {
          boundSessionId = event.sessionId;
        }
        onEvent(event);
      });

      // Stream ended cleanly.
      onStatus?.("idle");
      return boundSessionId;
    } catch (err) {
      if (isAborted()) {
        onStatus?.("idle");
        return boundSessionId;
      }
      // Network error — try to reconnect with backoff.
      if (attempt >= RECONNECT_DELAYS_MS.length) {
        onStatus?.("lost");
        onEvent({
          type: "error",
          message: `Connection lost after ${attempt} attempts: ${
            err instanceof Error ? err.message : String(err)
          }`,
        });
        return boundSessionId;
      }
      onStatus?.("reconnecting");
      await new Promise((resolve) => setTimeout(resolve, RECONNECT_DELAYS_MS[attempt]));
    }
  }

  onStatus?.("lost");
  return boundSessionId;
}

/**
 * Persist a completed chat turn.
 *
 * @param sessionId - Session ID.
 * @param userMessage - User's message.
 * @param assistantAnswer - Agent's answer.
 * @param toolResults - Tool results from the turn.
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
    // Persistence failure is non-fatal.
  }
}
