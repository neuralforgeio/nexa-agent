/**
 * Nexa Agent — LLM Provider
 *
 * Thin abstraction over the z-ai-web-dev-sdk. The provider owns the SDK
 * client and exposes a single chat_completion() entry point used by the
 * agent loop. Supports custom base URLs (OpenAI-compatible endpoints,
 * OpenRouter, etc.) conceptually; this build resolves the Nexa core model
 * through the bundled SDK.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import ZAI from "z-ai-web-dev-sdk";
import { NEXA_DEFAULT_MODEL, NEXA_NAME, NEXA_VERSION } from "./constants";
import type { ProviderMessage } from "./types";

let clientPromise: Promise<unknown> | null = null;

async function getClient() {
  if (!clientPromise) {
    clientPromise = ZAI.create();
  }
  return clientPromise;
}

export interface ChatCompletionOptions {
  messages: ProviderMessage[];
  /** Enable chain-of-thought reasoning. Default: disabled. */
  thinking?: boolean;
  /** Max tokens hint forwarded to the model. */
  maxTokens?: number;
}

export interface ChatCompletionResponse {
  content: string;
  model: string;
  raw?: unknown;
}

export class LLMProvider {
  readonly model: string;
  private readonly apiKey?: string;
  private readonly baseUrl?: string;

  constructor(opts?: { apiKey?: string; baseUrl?: string; model?: string }) {
    this.apiKey = opts?.apiKey;
    this.baseUrl = opts?.baseUrl;
    this.model = opts?.model ?? NEXA_DEFAULT_MODEL;
  }

  /**
   * Run a single chat completion round. The first message is treated as the
   * system prompt (role 'assistant' per SDK convention). Retries with
   * exponential backoff on transient errors (429 / 5xx).
   */
  async chatCompletion(
    options: ChatCompletionOptions
  ): Promise<ChatCompletionResponse> {
    const client = (await getClient()) as {
      chat: {
        completions: {
          create: (args: {
            messages: { role: string; content: string }[];
            thinking?: { type: "enabled" | "disabled" };
          }) => Promise<{
            choices?: { message?: { content?: string } }[];
          }>;
        };
      };
    };

    const messages = options.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const maxRetries = 4;
    let lastError: unknown = null;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const completion = await client.chat.completions.create({
          messages,
          thinking: { type: options.thinking ? "enabled" : "disabled" },
        });
        const content = completion.choices?.[0]?.message?.content ?? "";
        return {
          content,
          model: this.model,
          raw: completion,
        };
      } catch (err) {
        lastError = err;
        const isTransient = isTransientError(err);
        if (!isTransient || attempt === maxRetries - 1) break;
        // Exponential backoff: 1s, 2s, 4s, 8s
        const delayMs = 1000 * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
    const message =
      lastError instanceof Error ? lastError.message : String(lastError);
    throw new Error(message);
  }

  /**
   * Stream a chat completion token-by-token. Yields content deltas as they
   * arrive. Falls back to pseudo-streaming (chunking the full response) if
   * the SDK does not return an async iterable when `stream: true` is set.
   */
  async *chatCompletionStream(
    options: ChatCompletionOptions
  ): AsyncGenerator<string, void, unknown> {
    const client = (await getClient()) as {
      chat: {
        completions: {
          create: (args: {
            messages: { role: string; content: string }[];
            thinking?: { type: "enabled" | "disabled" };
            stream?: boolean;
          }) => Promise<unknown>;
        };
      };
    };

    const messages = options.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Attempt 1: true streaming via SDK.
    try {
      const result = await client.chat.completions.create({
        messages,
        thinking: { type: options.thinking ? "enabled" : "disabled" },
        stream: true,
      });
      // Determine the streaming response shape and handle accordingly.
      const isIterable = result && typeof (result as AsyncIterable<unknown>)[Symbol.asyncIterator] === "function";
      const isResponse = typeof Response !== "undefined" && result instanceof Response;
      const isReadableStream = typeof ReadableStream !== "undefined" && result instanceof ReadableStream;

      // Case A: Response object — read its body as SSE stream.
      if (isResponse && result.body) {
        const reader = (result as Response).body!.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          sseBuffer += decoder.decode(value, { stream: true });
          const lines = sseBuffer.split("\n");
          sseBuffer = lines.pop() ?? "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const data = trimmed.slice(5).trim();
            if (data === "[DONE]") return;
            try {
              const parsed = JSON.parse(data);
              const delta = extractDelta(parsed);
              if (delta) yield delta;
            } catch {
              /* skip non-JSON SSE line */
            }
          }
        }
        return;
      }

      // Case B: ReadableStream — decode and parse as SSE.
      if (isReadableStream) {
        const reader = (result as ReadableStream<Uint8Array>).getReader();
        const decoder = new TextDecoder();
        let sseBuffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          sseBuffer += decoder.decode(value, { stream: true });
          const lines = sseBuffer.split("\n");
          sseBuffer = lines.pop() ?? "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const data = trimmed.slice(5).trim();
            if (data === "[DONE]") return;
            try {
              const parsed = JSON.parse(data);
              const delta = extractDelta(parsed);
              if (delta) yield delta;
            } catch {
              /* skip */
            }
          }
        }
        return;
      }

      // Case C: async-iterable of objects/strings.
      if (isIterable) {
        for await (const chunk of result as AsyncIterable<unknown>) {
          if (typeof chunk === "string") {
            if (chunk) yield chunk;
          } else {
            const delta = extractDelta(chunk);
            if (delta) yield delta;
          }
        }
        return;
      }
      // If result is a string, pseudo-stream it directly.
      if (typeof result === "string" && result.length > 0) {
        yield* pseudoStream(result);
        return;
      }
      // If SDK returned a full response despite stream:true, fall through to pseudo-stream.
      const fullContent = extractFullContent(result);
      if (fullContent) {
        yield* pseudoStream(fullContent);
        return;
      }
    } catch (err) {
      // If streaming failed with a transient error, the non-stream retry in
      // chatCompletion will handle it. For non-transient, fall through to pseudo.
      if (isTransientError(err)) {
        // Let the non-stream path handle retries.
      } else {
        throw err;
      }
    }

    // Attempt 2: fallback — non-streaming call, then pseudo-stream the result.
    const response = await this.chatCompletion(options);
    yield* pseudoStream(response.content);
  }

  /** Stamp the system prompt with Nexa identity. */
  static buildSystemPrompt(body: string): string {
    return [
      `You are ${NEXA_NAME} v${NEXA_VERSION}, an advanced AI agent.`,
      "You reason step by step and may use tools to ground your answers.",
      "Be concise, accurate and helpful. When you use a tool, emit the tool",
      "call exactly in the documented format and stop; the runtime will",
      "execute it and feed the result back to you.",
      "",
      body,
    ].join("\n");
  }
}

/** Detect transient (retryable) errors: 429 rate-limit and 5xx server errors. */
function isTransientError(err: unknown): boolean {
  const text = err instanceof Error ? err.message : String(err);
  // The SDK surfaces HTTP status in the error message.
  if (/status 429/i.test(text)) return true;
  if (/status 5\d\d/i.test(text)) return true;
  if (/too many requests/i.test(text)) return true;
  if (/rate.?limit/i.test(text)) return true;
  if (/service unavailable/i.test(text)) return true;
  if (/gateway timeout/i.test(text)) return true;
  if (/ECONNRESET|ETIMEDOUT|fetch failed/i.test(text)) return true;
  return false;
}

/** Extract a text delta from a streamed chunk (tolerant of multiple shapes). */
function extractDelta(chunk: unknown): string {
  if (!chunk || typeof chunk !== "object") return "";
  const c = chunk as {
    choices?: { delta?: { content?: string }; message?: { content?: string } }[];
    content?: string;
    response?: string;
  };
  const choice = c.choices?.[0];
  if (choice) {
    return choice.delta?.content ?? choice.message?.content ?? "";
  }
  return c.content ?? c.response ?? "";
}

/** Extract full content from a non-streamed response object. */
function extractFullContent(result: unknown): string {
  if (!result || typeof result !== "object") return "";
  const r = result as {
    choices?: { message?: { content?: string } }[];
    content?: string;
  };
  return r.choices?.[0]?.message?.content ?? r.content ?? "";
}

/** Yield a string in small chunks to simulate token streaming. */
async function* pseudoStream(text: string): AsyncGenerator<string, void, unknown> {
  if (!text) return;
  // Chunk by ~3-word groups for a natural typing feel.
  const tokens = text.match(/\S+\s*/g) ?? [text];
  for (const tok of tokens) {
    yield tok;
    await new Promise((r) => setTimeout(r, 18));
  }
}
