/**
 * Nexa Agent — Notes Tools
 *
 * Tools that expose the per-session scratchpad to the agent loop. Notes are
 * working state for complex tasks — distinct from long-term memory.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NexaTool } from "./base";
import {
  clearNotes,
  createNote,
  listNotes,
} from "../notes";

/** The active session id is injected at request time via a module-level slot. */
let activeSessionId: string | null = null;

export function setActiveSessionId(id: string | null): void {
  activeSessionId = id;
}

export class SaveNoteTool extends NexaTool {
  readonly name = "save_note";
  readonly description =
    "Jot down a working note in the current session's scratchpad. Use for intermediate results, task checklists, or anything you want to track during this conversation. Notes are per-session and do not persist across sessions — use save_memory for durable facts.";
  readonly category = "memory" as const;
  readonly parameters = {
    content: {
      type: "string" as const,
      description: "The note text to save.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    if (!activeSessionId) {
      return this.fail("no active session for notes");
    }
    const content = String(args.content ?? "").trim();
    if (!content) return this.fail("content is required");
    const note = await createNote(activeSessionId, content);
    return this.ok(`note saved: ${note.content}`);
  }
}

export class ListNotesTool extends NexaTool {
  readonly name = "list_notes";
  readonly description =
    "List all working notes in the current session's scratchpad (pinned first, then newest). Useful to review intermediate state before continuing a complex task.";
  readonly category = "memory" as const;
  readonly parameters = {};

  async execute() {
    if (!activeSessionId) {
      return this.fail("no active session for notes");
    }
    const notes = await listNotes(activeSessionId);
    if (notes.length === 0) {
      return this.ok("scratchpad is empty");
    }
    const body = notes
      .map((n) => `${n.pinned ? "★" : "·"} ${n.content}`)
      .join("\n");
    return this.ok(`${notes.length} note(s) in scratchpad:\n${body}`);
  }
}

export class ClearNotesTool extends NexaTool {
  readonly name = "clear_notes";
  readonly description =
    "Clear all non-pinned working notes from the current session's scratchpad. Pinned notes are preserved. Use when the scratchpad is cluttered.";
  readonly category = "memory" as const;
  readonly parameters = {};

  async execute() {
    if (!activeSessionId) {
      return this.fail("no active session for notes");
    }
    const count = await clearNotes(activeSessionId);
    return this.ok(`cleared ${count} non-pinned note(s) from scratchpad`);
  }
}
