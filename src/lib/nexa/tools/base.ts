/**
 * Nexa Agent — Tool Base
 *
 * Abstract contract every Nexa tool implements. Tools are pure functions
 * with a schema descriptor so the agent loop can reason about them.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { ToolParameter, ToolResult, ToolSchema } from "../types";

export abstract class NexaTool {
  abstract readonly name: string;
  abstract readonly description: string;

  /** Parameter schema surfaced to the model. */
  abstract readonly parameters: Record<string, ToolParameter>;

  /** Human-readable category for UI grouping. */
  readonly category: "system" | "memory" | "utility" | "data" = "utility";

  getSchema(): ToolSchema {
    return {
      name: this.name,
      description: this.description,
      parameters: this.parameters,
    };
  }

  /** Execute the tool. Must never throw — return ok:false on failure. */
  abstract execute(
    args: Record<string, unknown>
  ): Promise<ToolResult> | ToolResult;

  /** Helper to build a successful result. */
  protected ok(output: string, durationMs = 0): ToolResult {
    return { tool: this.name, ok: true, output, durationMs };
  }

  /** Helper to build a failure result. */
  protected fail(output: string, durationMs = 0): ToolResult {
    return { tool: this.name, ok: false, output, durationMs };
  }
}
