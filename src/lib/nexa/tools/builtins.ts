/**
 * Nexa Agent — Built-in Tools
 *
 * The default tool set shipped with Nexa Agent v1.0.0. Each tool is a small,
 * self-contained capability the agent can invoke during a conversation.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import { NexaTool } from "./base";

/* ------------------------------------------------------------------ *
 * Echo — the canonical "is tool calling wired up?" smoke tool.
 * ------------------------------------------------------------------ */
export class EchoTool extends NexaTool {
  readonly name = "echo";
  readonly description =
    "Echo the provided text back to the terminal. Useful for debugging.";
  readonly category = "system" as const;
  readonly parameters = {
    text: {
      type: "string" as const,
      description: "The text to echo back.",
      required: true,
    },
  };

  execute(args: Record<string, unknown>) {
    const text = String(args.text ?? "");
    return this.ok(text);
  }
}

/* ------------------------------------------------------------------ *
 * GetTime — current timestamp in a configurable timezone/zone label.
 * ------------------------------------------------------------------ */
export class GetTimeTool extends NexaTool {
  readonly name = "get_time";
  readonly description =
    "Return the current date and time. Optionally accept an IANA timezone label (e.g. Asia/Jakarta) for display.";
  readonly category = "utility" as const;
  readonly parameters = {
    timezone: {
      type: "string" as const,
      description: "Optional IANA timezone, e.g. 'Asia/Jakarta'. Defaults to UTC.",
      required: false,
    },
  };

  execute(args: Record<string, unknown>) {
    const tz = String(args.timezone || "UTC");
    try {
      const now = new Date();
      const formatted = new Intl.DateTimeFormat("en-US", {
        dateStyle: "full",
        timeStyle: "long",
        timeZone: tz,
      }).format(now);
      return this.ok(`${formatted}\n(iso: ${now.toISOString()})\n(zone: ${tz})`);
    } catch {
      return this.fail(`Invalid timezone: ${tz}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * Calculate — safe arithmetic evaluator (no eval of arbitrary code).
 * ------------------------------------------------------------------ */
export class CalculateTool extends NexaTool {
  readonly name = "calculate";
  readonly description =
    "Evaluate a math expression containing +, -, *, /, parentheses, decimals and whitespace. Returns the numeric result.";
  readonly category = "utility" as const;
  readonly parameters = {
    expression: {
      type: "string" as const,
      description: "The arithmetic expression, e.g. '(12 + 8) * 3 / 5'.",
      required: true,
    },
  };

  private tokenize(expr: string): string[] {
    const tokens: string[] = [];
    let i = 0;
    while (i < expr.length) {
      const ch = expr[i];
      if (/\s/.test(ch)) {
        i++;
        continue;
      }
      if ("+-*/()".includes(ch)) {
        tokens.push(ch);
        i++;
        continue;
      }
      if (/[0-9.]/.test(ch)) {
        let num = "";
        while (i < expr.length && /[0-9.]/.test(expr[i])) {
          num += expr[i];
          i++;
        }
        tokens.push(num);
        continue;
      }
      throw new Error(`Unexpected character '${ch}'`);
    }
    return tokens;
  }

  private evaluate(tokens: string[]): number {
    let pos = 0;
    const peek = () => tokens[pos];
    const consume = () => tokens[pos++];

    const parsePrimary = (): number => {
      const tok = peek();
      if (tok === "(") {
        consume();
        const val = parseAddSub();
        if (peek() !== ")") throw new Error("Missing ')'");
        consume();
        return val;
      }
      if (tok === undefined) throw new Error("Unexpected end of expression");
      const n = Number(tok);
      if (Number.isNaN(n)) throw new Error(`Not a number: ${tok}`);
      consume();
      return n;
    };

    const parseMulDiv = (): number => {
      let left = parsePrimary();
      while (peek() === "*" || peek() === "/") {
        const op = consume();
        const right = parsePrimary();
        left = op === "*" ? left * right : left / right;
      }
      return left;
    };

    const parseAddSub = (): number => {
      let left = parseMulDiv();
      while (peek() === "+" || peek() === "-") {
        const op = consume();
        const right = parseMulDiv();
        left = op === "+" ? left + right : left - right;
      }
      return left;
    };

    const result = parseAddSub();
    if (pos < tokens.length) throw new Error("Unexpected trailing tokens");
    return result;
  }

  execute(args: Record<string, unknown>) {
    const expr = String(args.expression ?? "").trim();
    if (!expr) return this.fail("Empty expression.");
    try {
      const result = this.evaluate(this.tokenize(expr));
      if (!Number.isFinite(result)) {
        return this.fail("Result is not finite (division by zero?).");
      }
      const rounded = Math.round(result * 1e10) / 1e10;
      return this.ok(`${expr} = ${rounded}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`Could not evaluate: ${msg}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * GenerateUUID — produce a fresh UUID v4 for the agent to reference.
 * ------------------------------------------------------------------ */
export class GenerateUuidTool extends NexaTool {
  readonly name = "generate_uuid";
  readonly description =
    "Generate a random UUID v4 string. Useful for creating unique identifiers.";
  readonly category = "utility" as const;
  readonly parameters = {};

  execute() {
    const uuid = crypto.randomUUID();
    return this.ok(uuid);
  }
}

/* ------------------------------------------------------------------ *
 * Base64 — encode/decode helper.
 * ------------------------------------------------------------------ */
export class Base64Tool extends NexaTool {
  readonly name = "base64";
  readonly description =
    "Encode or decode a Base64 string. Pass mode 'encode' or 'decode'.";
  readonly category = "data" as const;
  readonly parameters = {
    mode: {
      type: "string" as const,
      description: "'encode' or 'decode'.",
      required: true,
    },
    value: {
      type: "string" as const,
      description: "The string to transform.",
      required: true,
    },
  };

  execute(args: Record<string, unknown>) {
    const mode = String(args.mode ?? "encode");
    const value = String(args.value ?? "");
    try {
      if (mode === "encode") {
        return this.ok(
          Buffer.from(value, "utf-8").toString("base64")
        );
      }
      if (mode === "decode") {
        return this.ok(
          Buffer.from(value, "base64").toString("utf-8")
        );
      }
      return this.fail(`Unknown mode: ${mode}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`Base64 error: ${msg}`);
    }
  }
}

/**
 * Factory that wires up the default Nexa tool set into a fresh registry.
 * Callers may pass extra tools to augment the defaults.
 */
export function createDefaultTools(extra: NexaTool[] = []): NexaTool[] {
  return [
    new EchoTool(),
    new GetTimeTool(),
    new CalculateTool(),
    new GenerateUuidTool(),
    new Base64Tool(),
    ...extra,
  ];
}
