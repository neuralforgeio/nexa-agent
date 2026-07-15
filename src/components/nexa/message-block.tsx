"use client";

import { Copy, Cpu, Terminal, User, Wrench } from "lucide-react";
import { useState } from "react";
import type { NexaMessage } from "@/lib/nexa/types";
import { Markdown } from "./markdown";

/**
 * Renders a single persisted message in the transcript.
 */
export function MessageBlock({ message }: { message: NexaMessage }) {
  const ts = formatTime(message.createdAt);

  if (message.role === "user") {
    return (
      <div className="flex justify-end nexa-fade-in">
        <div className="flex max-w-[85%] gap-2.5">
          <div className="order-2 flex flex-col items-center gap-1">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-muted">
              <User className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <span className="text-[9px] text-muted-foreground/50">{ts}</span>
          </div>
          <div className="order-1 space-y-1">
            <div className="rounded-lg rounded-tr-sm border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-sm text-foreground">
              <div className="whitespace-pre-wrap break-words">{message.content}</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return (
      <div className="ml-9 nexa-fade-in">
        <div className="rounded-md border border-border bg-black/30 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
            <Terminal className="h-3 w-3 text-emerald-400" />
            <span className="text-emerald-400">{message.toolName ?? "tool"}</span>
            <Wrench className="h-2.5 w-2.5" />
            <span>output</span>
            <span className="ml-auto text-muted-foreground/50 normal-case tracking-normal">
              {ts}
            </span>
          </div>
          <pre className="whitespace-pre-wrap break-words text-[11px] text-foreground/80 nexa-scroll overflow-x-auto max-h-40">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex max-w-full gap-2.5 nexa-fade-in">
      <div className="flex flex-col items-center gap-1">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10">
          <Cpu className="h-3.5 w-3.5 text-emerald-400" />
        </div>
        <span className="text-[9px] text-muted-foreground/50">{ts}</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          <span className="text-emerald-400 font-semibold">nexa</span>
          <span className="text-muted-foreground/60">agent</span>
          <CopyButton text={message.content} />
        </div>
        <div className="rounded-lg rounded-tl-sm border border-border bg-card/60 px-3.5 py-2.5">
          <Markdown content={message.content} />
        </div>
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
      aria-label="copy answer"
    >
      {copied ? (
        <span className="text-emerald-400">copied</span>
      ) : (
        <Copy className="h-2.5 w-2.5" />
      )}
    </button>
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
