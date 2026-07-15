/**
 * Nexa Agent — Tool Registry & Dispatcher
 *
 * Central registry that owns tool lifecycle. The agent loop queries the
 * registry for schemas (to advertise tools to the model) and dispatches
 * execution requests, timing each invocation.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { ToolRequest, ToolResult, ToolSchema } from "../types";
import { NexaTool } from "./base";

export class ToolRegistry {
  private readonly tools = new Map<string, NexaTool>();

  register(tool: NexaTool): this {
    if (this.tools.has(tool.name)) {
      throw new Error(`[nexa] tool already registered: ${tool.name}`);
    }
    this.tools.set(tool.name, tool);
    return this;
  }

  has(name: string): boolean {
    return this.tools.has(name);
  }

  get(name: string): NexaTool | undefined {
    return this.tools.get(name);
  }

  list(): NexaTool[] {
    return Array.from(this.tools.values());
  }

  /** Schemas advertised to the model. */
  schemas(): ToolSchema[] {
    return this.list().map((t) => t.getSchema());
  }

  /** Human-readable summary for the system prompt. */
  describe(): string {
    const lines = this.list().map((t) => {
      const params = Object.entries(t.parameters)
        .map(([key, p]) => `${key}: ${p.type}${p.required ? " (required)" : ""}`)
        .join(", ");
      return `- ${t.name} — ${t.description} [params: ${params || "none"}]`;
    });
    return lines.join("\n");
  }

  /** Dispatch a tool request, capturing timing. Never throws. */
  async execute(request: ToolRequest): Promise<ToolResult> {
    const tool = this.tools.get(request.tool);
    if (!tool) {
      return {
        tool: request.tool,
        ok: false,
        output: `Unknown tool: ${request.tool}`,
        durationMs: 0,
      };
    }
    const started = Date.now();
    try {
      const result = await tool.execute(request.arguments ?? {});
      return { ...result, durationMs: result.durationMs || Date.now() - started };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        tool: request.tool,
        ok: false,
        output: `Tool '${request.tool}' crashed: ${message}`,
        durationMs: Date.now() - started,
      };
    }
  }
}
