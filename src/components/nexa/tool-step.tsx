"use client";

import { useState } from "react";
import { ChevronRight, Terminal, Wrench } from "lucide-react";
import type { AgentStep } from "@/lib/nexa/types";

/**
 * Renders a tool-call + tool-result pair as a collapsible terminal card.
 */
export function ToolStepView({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);

  if (step.kind === "tool_call" && step.toolRequest) {
    const req = step.toolRequest;
    return (
      <div className="my-1.5 nexa-fade-in">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-2.5 py-1.5 text-left text-xs hover:bg-amber-500/10 transition-colors"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 text-amber-400 transition-transform ${open ? "rotate-90" : ""}`}
          />
          <Wrench className="h-3.5 w-3.5 text-amber-400" />
          <span className="font-semibold text-amber-300">{req.tool}</span>
          <span className="text-muted-foreground truncate">({formatArgs(req.arguments)})</span>
        </button>
        {open && (
          <div className="mt-1 ml-5 rounded-md border border-border bg-black/30 p-2.5 text-[11px]">
            <div className="text-muted-foreground mb-1">arguments:</div>
            <pre className="text-emerald-200/90 whitespace-pre-wrap break-all nexa-scroll overflow-x-auto">
              {JSON.stringify(req.arguments, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }

  if (step.kind === "tool_result" && step.toolResult) {
    const r = step.toolResult;
    return (
      <div className="my-1.5 ml-5 nexa-fade-in">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 py-1.5 text-left text-xs hover:bg-muted/70 transition-colors"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`}
          />
          <Terminal className={`h-3.5 w-3.5 ${r.ok ? "text-emerald-400" : "text-red-400"}`} />
          <span className={r.ok ? "text-emerald-300" : "text-red-300"}>
            {r.ok ? "ok" : "failed"}
          </span>
          <span className="text-muted-foreground">{r.tool}</span>
          <span className="text-muted-foreground/70 ml-auto">{r.durationMs}ms</span>
        </button>
        {open && (
          <div className="mt-1 rounded-md border border-border bg-black/30 p-2.5 text-[11px]">
            <div className="text-muted-foreground mb-1">output:</div>
            <pre className="whitespace-pre-wrap break-all text-foreground/90 nexa-scroll overflow-x-auto max-h-60">
              {r.output}
            </pre>
          </div>
        )}
      </div>
    );
  }

  return null;
}

function formatArgs(args: Record<string, unknown>): string {
  const parts = Object.entries(args).map(([k, v]) => {
    const val = typeof v === "string" ? `"${truncate(v, 30)}"` : String(v);
    return `${k}: ${val}`;
  });
  return parts.join(", ");
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
