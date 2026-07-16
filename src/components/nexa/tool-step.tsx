"use client";

import { useState } from "react";
import { ChevronRight, Wrench } from "lucide-react";
import type { AgentStep } from "@/lib/nexa/types";

export function ToolStepView({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);

  if (step.kind === "tool_call" && step.toolRequest) {
    const req = step.toolRequest;
    return (
      <div className="my-1.5 nexa-fade-in">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 rounded-lg border border-primary/20 bg-accent px-3 py-2 text-left transition-colors hover:bg-accent"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 text-primary transition-transform ${open ? "rotate-90" : ""}`}
          />
          <Wrench className="h-3.5 w-3.5 text-primary" />
          <span className="text-[13px] font-medium text-primary">{req.tool}</span>
          <span className="truncate font-mono text-[12px] text-tertiary">
            {formatArgs(req.arguments)}
          </span>
        </button>
        {open && (
          <div className="mt-1 ml-5 rounded-lg border border-border bg-secondary p-3">
            <div className="mb-1 text-[11px] text-tertiary">arguments</div>
            <pre className="nexa-scroll overflow-x-auto font-mono text-[12px] text-foreground/90">
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
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-secondary px-3 py-2 text-left transition-colors hover:bg-tertiary"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 text-tertiary transition-transform ${open ? "rotate-90" : ""}`}
          />
          <span
            className={`h-2 w-2 rounded-full ${r.ok ? "bg-success" : "bg-error"}`}
          />
          <span className={`text-[13px] font-medium ${r.ok ? "text-success" : "text-error"}`}>
            {r.ok ? "Success" : "Failed"}
          </span>
          <span className="text-[12px] text-tertiary">{r.tool}</span>
          <span className="ml-auto text-[11px] text-tertiary">{r.durationMs}ms</span>
        </button>
        {open && (
          <div className="mt-1 rounded-lg border border-border bg-secondary p-3">
            <div className="mb-1 text-[11px] text-tertiary">output</div>
            <pre className="nexa-scroll max-h-60 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[12px] text-foreground/90">
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
    const val = typeof v === "string" ? `"${truncate(v, 40)}"` : String(v);
    return `${k}: ${val}`;
  });
  return parts.join(", ");
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
