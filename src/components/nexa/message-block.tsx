"use client";

import { User, Cpu, Terminal } from "lucide-react";
import type { NexaMessage } from "@/lib/nexa/types";
import { Markdown } from "./markdown";

/**
 * Renders a single persisted message in the transcript.
 */
export function MessageBlock({ message }: { message: NexaMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end nexa-fade-in">
        <div className="flex max-w-[85%] gap-2.5">
          <div className="order-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-muted">
            <User className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="order-1 rounded-lg rounded-tr-sm border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-sm text-foreground">
            <div className="whitespace-pre-wrap break-words">{message.content}</div>
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
            <span>output</span>
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
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10">
        <Cpu className="h-3.5 w-3.5 text-emerald-400" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          <span className="text-emerald-400 font-semibold">nexa</span>
          <span className="text-muted-foreground/60">agent</span>
        </div>
        <div className="rounded-lg rounded-tl-sm border border-border bg-card/60 px-3.5 py-2.5">
          <Markdown content={message.content} />
        </div>
      </div>
    </div>
  );
}
