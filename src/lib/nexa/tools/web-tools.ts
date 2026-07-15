/**
 * Nexa Agent — Web Tools
 *
 * Tools that give the agent live access to the internet: web search and
 * page reading. Both are backed by the z-ai-web-dev-sdk function invoker,
 * so they run entirely server-side.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import ZAI from "z-ai-web-dev-sdk";
import { NexaTool } from "./base";

let sdkPromise: Promise<unknown> | null = null;
async function getSdk() {
  if (!sdkPromise) sdkPromise = ZAI.create();
  return sdkPromise as Promise<{
    functions: {
      invoke: (
        name: string,
        args: Record<string, unknown>
      ) => Promise<unknown>;
    };
  }>;
}

interface SearchHit {
  url?: string;
  name?: string;
  snippet?: string;
  host_name?: string;
  date?: string;
}

/* ------------------------------------------------------------------ *
 * WebSearch — live web search returning ranked results.
 * ------------------------------------------------------------------ */
export class WebSearchTool extends NexaTool {
  readonly name = "web_search";
  readonly description =
    "Search the live web for current information. Returns ranked results with title, url, snippet, source domain and date. Use this for anything time-sensitive or factual you don't already know.";
  readonly category = "utility" as const;
  readonly parameters = {
    query: {
      type: "string" as const,
      description: "The search query.",
      required: true,
    },
    num: {
      type: "number" as const,
      description: "Max results to return (1-10). Default 5.",
      required: false,
    },
  };

  async execute(args: Record<string, unknown>) {
    const query = String(args.query ?? "").trim();
    if (!query) return this.fail("query is required");
    const num = clamp(Number(args.num) || 5, 1, 10);
    try {
      const sdk = await getSdk();
      const raw = await sdk.functions.invoke("web_search", {
        query,
        num,
      });
      const hits = normalizeHits(raw);
      if (hits.length === 0) {
        return this.ok(`no web results for: ${query}`);
      }
      const body = hits
        .map((h, i) => {
          const date = h.date ? `  (${h.date})` : "";
          return `${i + 1}. ${h.name ?? "(untitled)"}${date}\n   ${h.url ?? ""}\n   ${h.snippet ?? ""}\n   — ${h.host_name ?? ""}`;
        })
        .join("\n\n");
      return this.ok(
        `web search "${query}" → ${hits.length} result(s):\n\n${body}`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`web search failed: ${msg}`);
    }
  }
}

/* ------------------------------------------------------------------ *
 * WebFetch — read a single URL's main content.
 * ------------------------------------------------------------------ */
export class WebFetchTool extends NexaTool {
  readonly name = "web_fetch";
  readonly description =
    "Fetch and extract the readable content of a single web page URL. Use after web_search to dive into a specific source, or when the user gives a direct link.";
  readonly category = "utility" as const;
  readonly parameters = {
    url: {
      type: "string" as const,
      description: "The absolute URL to fetch (https://... preferred).",
      required: true,
    },
  };

  async execute(args: Record<string, unknown>) {
    const url = String(args.url ?? "").trim();
    if (!url) return this.fail("url is required");
    if (!/^https?:\/\//i.test(url)) {
      return this.fail("url must start with http:// or https://");
    }
    try {
      const sdk = await getSdk();
      const raw = await sdk.functions.invoke("web_reader", { url });
      const text = stringifyReaderResult(raw);
      if (!text.trim()) {
        return this.fail(`no readable content at ${url}`);
      }
      // Cap the payload so we don't blow the context window.
      const capped =
        text.length > 4000 ? text.slice(0, 4000) + "\n…[truncated]" : text;
      return this.ok(`content of ${url}:\n\n${capped}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return this.fail(`web fetch failed: ${msg}`);
    }
  }
}

/* ----------------------------- helpers ---------------------------- */

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}

function normalizeHits(raw: unknown): SearchHit[] {
  if (Array.isArray(raw)) return raw as SearchHit[];
  if (raw && typeof raw === "object") {
    const r = raw as { results?: unknown; data?: unknown };
    if (Array.isArray(r.results)) return r.results as SearchHit[];
    if (Array.isArray(r.data)) return r.data as SearchHit[];
  }
  return [];
}

function stringifyReaderResult(raw: unknown): string {
  if (typeof raw === "string") return raw;
  if (raw && typeof raw === "object") {
    const r = raw as {
      content?: string;
      html?: string;
      text?: string;
      title?: string;
      markdown?: string;
    };
    const body =
      r.markdown ?? r.content ?? r.text ?? stripHtml(r.html ?? "") ?? "";
    const title = r.title ? `# ${r.title}\n\n` : "";
    return title + body;
  }
  return JSON.stringify(raw);
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
