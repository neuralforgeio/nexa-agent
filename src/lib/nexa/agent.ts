/**
 * Nexa Agent — Core Agent Loop
 *
 * NexaAgent orchestrates one conversation turn: assemble the system prompt
 * (identity + tools + memory), call the LLM, parse any tool calls, execute
 * them via the registry, feed results back, and repeat until the model
 * produces a final natural-language answer (or the iteration cap is hit).
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import {
  NEXA_MAX_CONTEXT_MESSAGES,
  NEXA_MAX_TOOL_ITERATIONS,
  NEXA_NAME,
  NEXA_VERSION,
} from "./constants";
import { renderMemoryDigest } from "./memory";
import { LLMProvider } from "./provider";
import type {
  AgentStep,
  AgentTurnResult,
  NexaMessage,
  ProviderMessage,
  ToolRequest,
} from "./types";
import { NexaTool } from "./tools/base";
import {
  Base64Tool,
  CalculateTool,
  EchoTool,
  GenerateUuidTool,
  GetTimeTool,
} from "./tools/builtins";
import {
  ListDirTool,
  ReadFileTool,
  RunTerminalCommandTool,
  WriteFileTool,
} from "./tools/fs-tools";
import {
  ForgetMemoryTool,
  ListMemoryTool,
  RecallMemoryTool,
  SaveMemoryTool,
} from "./tools/memory-tools";
import {
  ClearNotesTool,
  ListNotesTool,
  SaveNoteTool,
} from "./tools/notes-tools";
import { ToolRegistry } from "./tools/registry";
import { WebFetchTool, WebSearchTool } from "./tools/web-tools";

const TOOL_CALL_RE = /<tool_call>\s*([\s\S]*?)\s*<\/tool_call>/g;

/** Parse the first valid tool call out of a model response. Tolerant of
 *  several common malformations the model may produce. */
function parseToolCall(content: string): ToolRequest | null {
  // 1. Preferred: well-formed <tool_call>...</tool_call> blocks.
  const matches = [...content.matchAll(TOOL_CALL_RE)];
  for (const m of matches) {
    const req = safeParseRequest(m[1]);
    if (req) return req;
  }

  // 2. Unclosed <tool_call> tag — take everything after the first opening tag.
  const openOnly = content.match(/<tool_call>([\s\S]*?)$/i);
  if (openOnly) {
    const req = safeParseRequest(openOnly[1]);
    if (req) return req;
  }

  // 3. Fenced ```json block whose parsed object has a "tool" key.
  const fence = content.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) {
    const req = safeParseRequest(fence[1]);
    if (req) return req;
  }

  // 4. Bare JSON object that IS the response (model emitted JSON without
  //    tags). Only trust this when the trimmed content starts with '{' to
  //    avoid snatching illustrative JSON out of a natural-language answer.
  const trimmed = content.trim();
  if (trimmed.startsWith("{")) {
    const req = safeParseRequest(trimmed);
    if (req) return req;
    const firstObj = extractJsonObjects(content)[0];
    if (firstObj) {
      const r = safeParseRequest(firstObj);
      if (r) return r;
    }
  }

  // 5. Lenient "tool_name(args)" shorthand like `save_memory(...)`.
  const shorthand = content.match(
    /\b(echo|get_time|calculate|generate_uuid|base64|save_memory|recall_memory|list_memory|forget_memory|save_note|list_notes|clear_notes|read_file|write_file|list_dir|run_terminal_command|web_search|web_fetch)\s*\(\s*([\s\S]*?)\s*\)/i
  );
  if (shorthand) {
    const tool = shorthand[1].toLowerCase();
    const args = parseShorthandArgs(shorthand[2]);
    if (args) return { tool, arguments: args };
  }

  return null;
}

/** Extract top-level balanced JSON object substrings from a string. */
function extractJsonObjects(s: string): string[] {
  const results: string[] = [];
  let i = 0;
  while (i < s.length) {
    if (s[i] === "{") {
      let depth = 0;
      let inStr = false;
      let esc = false;
      let j = i;
      for (; j < s.length; j++) {
        const c = s[j];
        if (inStr) {
          if (esc) esc = false;
          else if (c === "\\") esc = true;
          else if (c === '"') inStr = false;
        } else if (c === '"') inStr = true;
        else if (c === "{") depth++;
        else if (c === "}") {
          depth--;
          if (depth === 0) {
            results.push(s.slice(i, j + 1));
            break;
          }
        }
      }
      i = j + 1;
    } else {
      i++;
    }
  }
  return results;
}

/** Parse a shorthand arg string like `"hello", kind: "note"` into a record. */
function parseShorthandArgs(raw: string): Record<string, unknown> | null {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  // Try JSON object form first.
  const asObj = safeParseRequest(`{${trimmed}}`);
  if (asObj) return asObj.arguments;
  // Try JSON array of positional → map to first param names heuristically.
  try {
    const arr = JSON.parse(`[${trimmed}]`);
    if (Array.isArray(arr)) {
      const out: Record<string, unknown> = {};
      arr.forEach((v, idx) => {
        out[`arg${idx}`] = v;
      });
      return out;
    }
  } catch {
    /* ignore */
  }
  return { value: trimmed };
}

function safeParseRequest(raw: string): ToolRequest | null {
  // First try strict JSON.
  try {
    const obj = JSON.parse(raw.trim());
    if (isValidToolRequest(obj)) return toToolRequest(obj);
  } catch {
    /* fall through to repair */
  }
  // Try repairing common JSON malformations the model produces.
  const repaired = repairJson(raw.trim());
  if (repaired !== raw.trim()) {
    try {
      const obj = JSON.parse(repaired);
      if (isValidToolRequest(obj)) return toToolRequest(obj);
    } catch {
      /* still broken */
    }
  }
  return null;
}

function isValidToolRequest(obj: unknown): obj is { tool: string; arguments?: unknown } {
  return (
    !!obj &&
    typeof obj === "object" &&
    typeof (obj as { tool?: unknown }).tool === "string" &&
    (!(obj as { arguments?: unknown }).arguments ||
      typeof (obj as { arguments?: unknown }).arguments === "object")
  );
}

function toToolRequest(obj: { tool: string; arguments?: unknown }): ToolRequest {
  return {
    tool: obj.tool,
    arguments: (obj.arguments ?? {}) as Record<string, unknown>,
  };
}

/**
 * Repair common JSON malformations the model produces:
 * - `"key" {` → `"key": {`  (missing colon after key)
 * - `"key"value` → `"key": "value"` (missing colon + space)
 * - trailing comma before `}` or `]`
 */
function repairJson(s: string): string {
  let out = s;
  // Fix missing colon between key and value: "key" {  or  "key" "
  out = out.replace(/"(\w+)"\s*(?=["{[\d\-])/g, '"$1": ');
  // Remove trailing commas
  out = out.replace(/,\s*([}\]])/g, "$1");
  return out;
}

/** Strip tool-call markup so the user never sees raw scaffolding. */
function stripToolMarkup(content: string): string {
  const stripped = content
    .replace(TOOL_CALL_RE, "")
    .replace(/<tool_call>[\s\S]*$/i, "")
    .replace(/<\/?tool_call>/gi, "")
    .replace(/```(?:json)?\s*[\s\S]*?```/g, "")
    .trim();
  // If stripping removed everything (the content was ONLY tool-call markup),
  // return empty so the caller can fall back to a clean message instead of
  // showing raw markup.
  return stripped;
}

export interface NexaAgentOptions {
  provider?: LLMProvider;
  tools?: NexaTool[];
}

export class NexaAgent {
  readonly provider: LLMProvider;
  readonly registry: ToolRegistry;

  constructor(opts: NexaAgentOptions = {}) {
    this.provider = opts.provider ?? new LLMProvider();
    this.registry = new ToolRegistry();
    for (const tool of opts.tools ?? createDefaultToolSet()) {
      this.registry.register(tool);
    }
  }

  /**
   * Run a single conversation turn against the given transcript.
   * `history` is treated as read-only; the agent appends internally.
   * Returns the assistant's final answer plus a replayable step log.
   */
  async runConversation(
    userInput: string,
    history: NexaMessage[] = []
  ): Promise<AgentTurnResult> {
    const steps: AgentStep[] = [];
    const now = () => new Date().toISOString();

    const systemPrompt = await this.buildSystemPrompt();
    const transcript: ProviderMessage[] = [{ role: "system", content: systemPrompt }];

    // Carry over recent history (trimmed to the context window).
    const trimmed = history.slice(-NEXA_MAX_CONTEXT_MESSAGES);
    for (const m of trimmed) {
      if (m.role === "system") continue;
      transcript.push({ role: m.role, content: m.content });
    }
    transcript.push({ role: "user", content: userInput });

    let iterations = 0;
    let lastContent = "";

    while (iterations < NEXA_MAX_TOOL_ITERATIONS) {
      iterations += 1;
      const response = await this.provider.chatCompletion({
        messages: transcript,
        thinking: false,
      });
      lastContent = response.content;

      const toolRequest = parseToolCall(response.content);
      if (!toolRequest) {
        // Final answer. If stripping removes everything (content was only
        // malformed tool-call markup), return a clean fallback message
        // instead of leaking raw scaffolding to the user.
        const stripped = stripToolMarkup(response.content);
        const answer = stripped || "[Nexa] I tried to call a tool but the request was malformed. Please rephrase and try again.";
        steps.push({
          kind: "answer",
          text: answer,
          at: now(),
        });
        return { answer, steps, iterations };
      }

      // Record the tool call.
      steps.push({
        kind: "tool_call",
        toolRequest,
        at: now(),
      });

      // Execute the tool.
      const result = await this.registry.execute(toolRequest);
      steps.push({
        kind: "tool_result",
        toolResult: result,
        at: now(),
      });

      // Feed the result back to the model.
      transcript.push({
        role: "assistant",
        content: response.content,
      });
      transcript.push({
        role: "tool",
        content: `Tool '${result.tool}' returned (ok=${result.ok}, ${result.durationMs}ms):\n${result.output}`,
      });
    }

    // Iteration cap reached — return whatever we have.
    const answer =
      stripToolMarkup(lastContent) ||
      `[${NEXA_NAME}] reached the tool-call iteration cap (${NEXA_MAX_TOOL_ITERATIONS}).`;
    steps.push({ kind: "answer", text: answer, at: now() });
    return { answer, steps, iterations };
  }

  /** Compose the system prompt: identity, tool catalog, memory digest. */
  private async buildSystemPrompt(): Promise<string> {
    const memoryDigest = await renderMemoryDigest();
    const toolCatalog = this.registry.describe();

    return LLMProvider.buildSystemPrompt(
      [
        `# Tools`,
        `You have access to the following tools. To call a tool, output ONLY`,
        `a tool-call block in this EXACT format — nothing before or after:`,
        ``,
        `<tool_call>`,
        `{"tool": "TOOL_NAME", "arguments": {"PARAM": VALUE}}`,
        `</tool_call>`,
        ``,
        `### Worked example`,
        `If the user says "remember that I like tea", reply with EXACTLY:`,
        ``,
        `<tool_call>`,
        `{"tool": "save_memory", "arguments": {"kind": "preference", "content": "user likes tea"}}`,
        `</tool_call>`,
        ``,
        `Do NOT wrap the tool call in markdown fences. Do NOT add prose like`,
        `"I'll save that". Output the <tool_call> block and stop. The runtime`,
        `executes the tool and returns the result; you then give the final answer.`,
        ``,
        `Rules:`,
        `- Call at most ONE tool per turn.`,
        `- After receiving a tool result, either call another tool or answer directly.`,
        `- Never invent tools outside the catalog below.`,
        `- If no tool is needed, answer the user in natural language with no tags.`,
        ``,
        `## Tool catalog`,
        toolCatalog,
        ``,
        `# Long-term memory`,
        `The following memories are already known (newest first):`,
        memoryDigest,
        ``,
        `Use save_memory to remember durable facts, recall_memory to search,`,
        `and forget_memory to remove outdated entries.`,
      ].join("\n")
    );
  }
}

/** Convenience factory bundling the default tool set with memory + web + notes + fs tools. */
export function createDefaultToolSet(): NexaTool[] {
  return [
    new EchoTool(),
    new GetTimeTool(),
    new CalculateTool(),
    new GenerateUuidTool(),
    new Base64Tool(),
    new SaveMemoryTool(),
    new RecallMemoryTool(),
    new ListMemoryTool(),
    new ForgetMemoryTool(),
    new WebSearchTool(),
    new WebFetchTool(),
    new SaveNoteTool(),
    new ListNotesTool(),
    new ClearNotesTool(),
    new ReadFileTool(),
    new WriteFileTool(),
    new ListDirTool(),
    new RunTerminalCommandTool(),
  ];
}

export { NEXA_NAME, NEXA_VERSION };
