/**
 * Nexa Agent — Shared Type Definitions
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

/** A single chat message in the conversation transcript. */
export interface NexaMessage {
  id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  /** Present when this message is the result of a tool execution. */
  toolName?: string;
  toolCallId?: string;
  createdAt: string;
}

/** Minimal message shape handed to the LLM provider. */
export interface ProviderMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
}

/** JSON-schema-ish descriptor exposed to the model for a tool. */
export interface ToolSchema {
  name: string;
  description: string;
  parameters: Record<string, ToolParameter>;
}

export interface ToolParameter {
  type: "string" | "number" | "boolean";
  description: string;
  required?: boolean;
}

/** A request issued by the agent to invoke a tool. */
export interface ToolRequest {
  tool: string;
  arguments: Record<string, unknown>;
}

/** Structured result of executing a tool. */
export interface ToolResult {
  tool: string;
  ok: boolean;
  output: string;
  /** Wall-clock execution time in milliseconds. */
  durationMs: number;
}

/** A single step recorded in the agent loop, for UI replay. */
export interface AgentStep {
  kind: "thinking" | "tool_call" | "tool_result" | "answer";
  text?: string;
  toolRequest?: ToolRequest;
  toolResult?: ToolResult;
  at: string;
}

/** Full transcript of one agent turn (one user input -> final answer). */
export interface AgentTurnResult {
  answer: string;
  steps: AgentStep[];
  /** Total LLM round-trips performed. */
  iterations: number;
}

/** A persisted conversation session. */
export interface NexaSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

/** A memory record persisted across sessions. */
export interface NexaMemory {
  id: string;
  kind: "note" | "fact" | "preference" | "skill";
  content: string;
  createdAt: string;
}

/** Events emitted by NexaAgent.runStreaming() for live UI updates. */
export type StreamEvent =
  | { type: "thinking" }
  | { type: "token"; text: string }
  | { type: "tool_call"; toolRequest: ToolRequest }
  | { type: "tool_result"; toolResult: ToolResult }
  | { type: "done"; answer: string; steps: AgentStep[]; iterations: number }
  | { type: "error"; message: string };
