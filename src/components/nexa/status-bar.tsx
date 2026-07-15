"use client";

import { Circle, Loader2, Wifi } from "lucide-react";
import { NEXA_DEFAULT_MODEL, NEXA_VERSION } from "@/lib/nexa/constants";

interface StatusBarProps {
  sessionId: string | null;
  messageCount: number;
  status: "idle" | "thinking" | "error";
}

export function StatusBar({ sessionId, messageCount, status }: StatusBarProps) {
  return (
    <div className="flex items-center gap-3 border-t border-border bg-sidebar/60 px-3 py-1.5 text-[11px] text-muted-foreground backdrop-blur">
      <span className="flex items-center gap-1.5">
        <Wifi className="h-3 w-3 text-emerald-400" />
        <span className="text-emerald-400">nexa-core</span>
      </span>
      <Sep />
      <span>model: {NEXA_DEFAULT_MODEL}</span>
      <Sep />
      <span className="hidden sm:inline">v{NEXA_VERSION}</span>
      <Sep className="hidden sm:inline" />
      <span className="truncate hidden md:inline">
        session: {sessionId ? sessionId.slice(0, 12) + "…" : "—"}
      </span>
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden sm:inline">{messageCount} msg</span>
        <Sep className="hidden sm:inline" />
        <span className="flex items-center gap-1.5">
          {status === "thinking" ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-amber-400" />
              <span className="text-amber-400">running</span>
            </>
          ) : status === "error" ? (
            <>
              <Circle className="h-2.5 w-2.5 fill-red-500 text-red-500" />
              <span className="text-red-400">error</span>
            </>
          ) : (
            <>
              <Circle className="h-2.5 w-2.5 fill-emerald-500 text-emerald-500 nexa-pulse-dot" />
              <span className="text-emerald-400">ready</span>
            </>
          )}
        </span>
      </div>
    </div>
  );
}

function Sep({ className = "" }: { className?: string }) {
  return <span className={`text-border ${className}`}>|</span>;
}
