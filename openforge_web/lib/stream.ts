/**
 * Nexa Agent — streaming helpers for the Web UI.
 *
 * Wraps fetch+SSE parsing, exposes chat + persistence calls used by page.tsx.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { ChatEvent, SessionMessage } from "./theme";

/** v4.7.0: pub-sub status for UI banners (F-01 stop button UI + F-08 banner). */
export type ConnectionStatus = "connected" | "reconnecting" | "lost" | "idle";

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000];

/**
 * Parse a ReadableStream of SSE text into discrete {@link ChatEvent}s.
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (event: ChatEvent) => void
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      // SSE payload may include multiple "data:" lines per event frame.
      const dataLines = raw
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart());
      if (dataLines.length === 0) continue;
      try {
        onEvent(JSON.parse(dataLines.join("")) as ChatEvent);
      } catch {
        // Malformed payload — skip to next event.
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
