"use client";

import { useEffect, useState } from "react";
import {
  MessageSquarePlus,
  Plus,
  Trash2,
  X,
  Cpu,
  Zap,
} from "lucide-react";
import { NEXA_AUTHOR, NEXA_VERSION } from "@/lib/nexa/constants";

export interface SessionItem {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

interface SidebarProps {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
  onClose?: () => void;
}

export function Sidebar({
  activeId,
  onSelect,
  onNew,
  refreshKey,
  onClose,
}: SidebarProps) {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch("/api/sessions", { cache: "no-store" });
        const data = await res.json();
        if (!cancelled) setSessions(data.sessions ?? []);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    setSessions((s) => s.filter((x) => x.id !== id));
    if (activeId === id) onSelect("");
  };

  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-sidebar/40">
      {/* brand header */}
      <div className="flex items-center gap-2.5 border-b border-border px-3 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-emerald-500/40 bg-emerald-500/10">
          <Zap className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-bold tracking-tight text-foreground">
              NEXA
            </span>
            <span className="rounded bg-emerald-500/15 px-1 py-px text-[9px] font-semibold text-emerald-400">
              v{NEXA_VERSION}
            </span>
          </div>
          <div className="truncate text-[10px] text-muted-foreground">
            agent runtime
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
            aria-label="close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* new session */}
      <div className="p-2.5">
        <button
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20"
        >
          <MessageSquarePlus className="h-4 w-4" />
          new session
        </button>
      </div>

      {/* sessions list */}
      <div className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        sessions
      </div>
      <div className="flex-1 overflow-y-auto nexa-scroll px-1.5 pb-2 space-y-0.5">
        {loading && (
          <div className="space-y-1.5 px-1 py-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded-md bg-muted/40" />
            ))}
          </div>
        )}
        {!loading && sessions.length === 0 && (
          <div className="px-2 py-6 text-center">
            <Cpu className="mx-auto mb-2 h-7 w-7 text-muted-foreground/40" />
            <p className="text-xs text-muted-foreground">
              no sessions yet.
              <br />
              send a message to begin.
            </p>
          </div>
        )}
        {sessions.map((s) => {
          const active = s.id === activeId;
          return (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              className={`group flex w-full items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors ${
                active
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-transparent hover:border-border hover:bg-muted/40"
              }`}
            >
              <div
                className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                  active ? "bg-emerald-400" : "bg-muted-foreground/40"
                }`}
              />
              <div className="min-w-0 flex-1">
                <div
                  className={`truncate text-xs font-medium ${
                    active ? "text-emerald-200" : "text-foreground/90"
                  }`}
                >
                  {s.title}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span>{relativeTime(s.updatedAt)}</span>
                  <span>·</span>
                  <span>{s.messageCount} msg</span>
                </div>
              </div>
              <Trash2
                onClick={(e) => remove(s.id, e)}
                className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
              />
            </button>
          );
        })}
      </div>

      {/* footer */}
      <div className="border-t border-border px-3 py-2.5">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Plus className="h-3 w-3" />
          <span>by {NEXA_AUTHOR}</span>
        </div>
        <div className="mt-0.5 text-[10px] text-muted-foreground/60">
          MIT License · © 2026
        </div>
      </div>
    </aside>
  );
}

function relativeTime(iso: string): string {
  const d = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - d);
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
