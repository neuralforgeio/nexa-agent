/**
 * Nexa Agent — Memory Tools
 *
 * Tools that expose the persistent memory system to the agent loop.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NexaTool } from "./base";
import {
  deleteMemory,
  listMemory,
  recallMemory,
  saveMemory,
  type MemoryKind,
} from "../memory";

export class SaveMemoryTool extends NexaTool {
  readonly name = "save_memory";
  readonly description =
    "Persist a durable note for future sessions. Use for facts about the user, preferences, or anything worth remembering long-term.";
  readonly category = "memory" as const;
  readonly parameters = {
    kind: {
      type: "string" as const,
      description:
        "Category of memory: 'note', 'fact', 'preference', or 'skill'.",
      required: true,
    },
    content: {
      type: "string" as const,
      description: "The memory text to store.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const kind = String(args.kind ?? "note") as MemoryKind;
    const content = String(args.content ?? "").trim();
    if (!content) return this.fail("content is required");
    if (!["note", "fact", "preference", "skill"].includes(kind)) {
      return this.fail(`invalid kind: ${kind}`);
    }
    const mem = await saveMemory(kind, content);
    return this.ok(`memory saved [${mem.kind}]: ${mem.content}`);
  }
}

export class RecallMemoryTool extends NexaTool {
  readonly name = "recall_memory";
  readonly description =
    "Search previously stored memories by keyword. Returns matching notes, facts and preferences.";
  readonly category = "memory" as const;
  readonly parameters = {
    query: {
      type: "string" as const,
      description: "Keyword to search for. Pass empty to list recent memories.",
      required: false,
    },
  };

  async execute(args: Record<string, unknown>) {
    const query = String(args.query ?? "");
    const items = await recallMemory(query, 8);
    if (items.length === 0) {
      return this.ok("no matching memories found");
    }
    const body = items
      .map((m) => `- [${m.kind}] ${m.content}`)
      .join("\n");
    return this.ok(`found ${items.length} memory item(s):\n${body}`);
  }
}

export class ListMemoryTool extends NexaTool {
  readonly name = "list_memory";
  readonly description =
    "List all stored memories, newest first. Useful to audit what the agent currently remembers.";
  readonly category = "memory" as const;
  readonly parameters = {};

  async execute() {
    const items = await listMemory(50);
    if (items.length === 0) return this.ok("memory store is empty");
    const body = items.map((m) => `- [${m.kind}] ${m.content}`).join("\n");
    return this.ok(`${items.length} memory item(s):\n${body}`);
  }
}

export class ForgetMemoryTool extends NexaTool {
  readonly name = "forget_memory";
  readonly description =
    "Delete a stored memory by matching keyword (removes the first match). Use when a fact is outdated or wrong.";
  readonly category = "memory" as const;
  readonly parameters = {
    query: {
      type: "string" as const,
      description: "Keyword identifying the memory to forget.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const query = String(args.query ?? "").trim();
    if (!query) return this.fail("query is required");
    const items = await recallMemory(query, 1);
    if (items.length === 0) return this.fail(`no memory matched '${query}'`);
    await deleteMemory(items[0].id);
    return this.ok(`forgot: ${items[0].content}`);
  }
}
