"use client";

import { Circle, Loader2 } from "lucide-react";
import { NEXA_DEFAULT_MODEL, NEXA_VERSION } from "@/lib/nexa/constants";

interface StatusBarProps {
  sessionId: string | null;
  messageCount: number;
  status: "idle" | "thinking" | "error";
}

export function StatusBar({ sessionId, messageCount, status }: StatusBarProps) {
  return (
    <div className="flex items-center gap-2.5 border-t border-border bg-secondary px-4 py-1.5 text-[11px] text-tertiary">
      <span className="flex items-center gap-1">
        {status === "thinking" ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin text-primary" />
            <span className="text-primary">running</span>
          </>
        ) : status === "error" ? (
          <>
            <Circle className="h-2 w-2 fill-error text-error" />
            <span className="text-error">error</span>
          </>
        ) : (
          <>
            <Circle className="h-2 w-2 fill-success text-success nexa-pulse" />
            <span className="text-success">ready</span>
          </>
        )}
      </span>
      <span className="text-border">·</span>
      <span>model: {NEXA_DEFAULT_MODEL}</span>
      <span className="text-border">·</span>
      <span>v{NEXA_VERSION}</span>
      <span className="text-border hidden sm:inline">·</span>
      <span className="hidden sm:inline">
        {sessionId ? `${sessionId.slice(0, 8)}…` : "no session"}
      </span>
      <span className="ml-auto hidden sm:inline">
        {messageCount} message{messageCount !== 1 ? "s" : ""}
      </span>
    </div>
  );
}
