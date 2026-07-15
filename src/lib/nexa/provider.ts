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
   * system prompt (role 'assistant' per SDK convention).
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
