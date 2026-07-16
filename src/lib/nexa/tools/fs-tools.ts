/**
 * Nexa Agent — File & Terminal Tools (Phase 2)
 *
 * Real filesystem and shell tools that let the agent manipulate the local
 * workspace. File operations are sandboxed to NEXA_WORKSPACE to prevent
 * arbitrary access to the host. Terminal commands run with a timeout and
 * output cap.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { NexaTool } from "./base";
import { NEXA_WORKSPACE } from "../constants";

/** Resolve a path safely inside the workspace, rejecting escapes. */
async function resolveInWorkspace(raw: string): Promise<string> {
  const base = await fs.mkdir(NEXA_WORKSPACE, { recursive: true }).then(() =>
    path.resolve(NEXA_WORKSPACE)
  );
  const resolved = path.resolve(base, raw);
  const rel = path.relative(base, resolved);
  if (rel.startsWith("..") || path.isAbsolute(raw)) {
    throw new Error(
      `path '${raw}' escapes the nexa workspace (${NEXA_WORKSPACE})`
    );
  }
  return resolved;
}

/* ------------------------------------------------------------------ *
 * ReadFile — read a text file from the workspace.
 * ------------------------------------------------------------------ */
export class ReadFileTool extends NexaTool {
  readonly name = "read_file";
  readonly description =
    "Read the contents of a text file inside the nexa workspace. Path is relative to the workspace root. Returns the file content (truncated to 4000 chars).";
  readonly category = "utility" as const;
  readonly parameters = {
    path: {
      type: "string" as const,
      description: "Relative path to the file inside the workspace, e.g. 'notes.txt' or 'src/app.py'.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const rel = String(args.path ?? "").trim();
    if (!rel) return this.fail("path is required");
    try {
      const full = await resolveInWorkspace(rel);
      const stat = await fs.stat(full);
      if (stat.isDirectory()) {
        return this.fail(`'${rel}' is a directory, not a file. Use list_dir to inspect it.`);
      }
      if (stat.size > 100_000) {
        return this.fail(`file is too large (${stat.size} bytes, max 100KB)`);
      }
      const content = await fs.readFile(full, "utf-8");
      const capped =
        content.length > 4000
          ? content.slice(0, 4000) + "\n…[truncated, " + content.length + " chars total]"
          : content;
      return this.ok(capped);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`could not read '${rel}': ${msg}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * WriteFile — write/create a file in the workspace (creates parent dirs).
 * ------------------------------------------------------------------ */
export class WriteFileTool extends NexaTool {
  readonly name = "write_file";
  readonly description =
    "Write text content to a file inside the nexa workspace. Overwrites if the file exists, creates it (and parent directories) if it doesn't.";
  readonly category = "utility" as const;
  readonly parameters = {
    path: {
      type: "string" as const,
      description: "Relative path to the file inside the workspace.",
      required: true,
    },
    content: {
      type: "string" as const,
      description: "The text content to write.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const rel = String(args.path ?? "").trim();
    const content = String(args.content ?? "");
    if (!rel) return this.fail("path is required");
    try {
      const full = await resolveInWorkspace(rel);
      await fs.mkdir(path.dirname(full), { recursive: true });
      await fs.writeFile(full, content, "utf-8");
      const bytes = Buffer.byteLength(content, "utf-8");
      return this.ok(`wrote ${bytes} bytes to ${rel}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`could not write '${rel}': ${msg}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * ListDir — list entries in a workspace directory.
 * ------------------------------------------------------------------ */
export class ListDirTool extends NexaTool {
  readonly name = "list_dir";
  readonly description =
    "List the files and subdirectories inside a directory in the nexa workspace. Pass '.' for the workspace root.";
  readonly category = "utility" as const;
  readonly parameters = {
    path: {
      type: "string" as const,
      description: "Relative directory path. Default '.' (workspace root).",
      required: false,
    },
  };

  async execute(args: Record<string, unknown>) {
    const rel = String(args.path ?? ".").trim() || ".";
    try {
      const full = await resolveInWorkspace(rel);
      const entries = await fs.readdir(full, { withFileTypes: true });
      if (entries.length === 0) {
        return this.ok(`'${rel}' is empty`);
      }
      const lines = entries
        .sort((a, b) => {
          if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
          return a.name.localeCompare(b.name);
        })
        .map((e) => {
          const tag = e.isDirectory() ? "📁" : "📄";
          return `${tag} ${e.name}`;
        });
      return this.ok(
        `contents of '${rel}' (${entries.length} entries):\n${lines.join("\n")}`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`could not list '${rel}': ${msg}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * RunTerminalCommand — execute a shell command in the workspace.
 * ------------------------------------------------------------------ */
const BLOCKED = [
  "rm -rf /",
  "mkfs",
  "dd if=",
  ":(){ :|:& };:",
  "shutdown",
  "reboot",
  "halt",
  "poweroff",
];

export class RunTerminalCommandTool extends NexaTool {
  readonly name = "run_terminal_command";
  readonly description =
    "Execute a shell command in the nexa workspace and return stdout/stderr. Use for tasks like creating folders, listing files, running scripts, checking git status, etc. Output is capped at 2000 chars. Commands run with a 15-second timeout.";
  readonly category = "utility" as const;
  readonly parameters = {
    command: {
      type: "string" as const,
      description: "The shell command to execute, e.g. 'mkdir -p src && echo done' or 'ls -la'.",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const command = String(args.command ?? "").trim();
    if (!command) return this.fail("command is required");

    const lower = command.toLowerCase();
    for (const bad of BLOCKED) {
      if (lower.includes(bad)) {
        return this.fail(`blocked command pattern detected: '${bad}'`);
      }
    }

    return new Promise((resolve) => {
      const child = spawn(command, {
        cwd: NEXA_WORKSPACE,
        shell: true,
        timeout: 15_000,
        env: { ...process.env, TERM: "dumb" },
      });
      let stdout = "";
      let stderr = "";
      let killed = false;

      child.stdout?.on("data", (d: Buffer) => {
        stdout += d.toString();
        if (stdout.length > 3000) child.kill("SIGKILL");
      });
      child.stderr?.on("data", (d: Buffer) => {
        stderr += d.toString();
        if (stderr.length > 3000) child.kill("SIGKILL");
      });
      child.on("error", (err) => {
        resolve(this.fail(`failed to spawn: ${err.message}`));
      });
      child.on("close", (code) => {
        const sig = (child.signalCode ?? "") as string;
        killed = sig === "SIGKILL" || sig === "SIGTERM";
        const cap = (s: string, n: number) =>
          s.length > n ? s.slice(0, n) + `\n…[truncated, ${s.length} chars total]` : s;
        const out = cap(stdout, 2000);
        const err2 = cap(stderr, 1000);
        const parts: string[] = [];
        parts.push(`exit code: ${code}${killed ? " (killed — output or time limit)" : ""}`);
        if (out) parts.push(`stdout:\n${out}`);
        if (err2) parts.push(`stderr:\n${err2}`);
        if (!out && !err2) parts.push("(no output)");
        resolve(this.ok(parts.join("\n\n")));
      });
    });
  }
}
