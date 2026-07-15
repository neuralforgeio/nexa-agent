"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Cpu,
  Download,
  Edit3,
  MessageSquarePlus,
  Plus,
  Trash2,
  X,
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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) editRef.current?.focus();
  }, [editingId]);

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

  const startRename = (s: SessionItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(s.id);
    setEditValue(s.title);
  };

  const commitRename = async (id: string) => {
    const title = editValue.trim();
    setEditingId(null);
    if (!title) return;
    setSessions((s) =>
      s.map((x) => (x.id === id ? { ...x, title } : x))
    );
    await fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
  };

  const exportSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    window.open(`/api/export/${id}`, "_blank");
  };

  const clearAll = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setTimeout(() => setConfirmClear(false), 3000);
      return;
    }
    await Promise.all(
      sessions.map((s) =>
        fetch(`/api/sessions/${s.id}`, { method: "DELETE" })
      )
    );
    setSessions([]);
    setConfirmClear(false);
    onSelect("");
  };

  const totalMsgs = sessions.reduce((a, s) => a + s.messageCount, 0);

  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-sidebar/40">
      {/* brand header */}
      <div className="flex items-center gap-2.5 border-b border-border px-3 py-3">
        <div className="relative flex h-8 w-8 items-center justify-center rounded-md border border-emerald-500/40 bg-emerald-500/10">
          <Zap className="h-4 w-4 text-emerald-400" />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400 nexa-pulse-dot" />
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

      {/* sessions header with clear-all */}
      <div className="flex items-center justify-between px-2.5 pb-1">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          sessions
          <span className="ml-1.5 rounded bg-muted/60 px-1 py-px text-[9px] text-muted-foreground/80">
            {sessions.length}
          </span>
        </div>
        {sessions.length > 0 && (
          <button
            onClick={clearAll}
            className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              confirmClear
                ? "bg-red-500/20 text-red-300"
                : "text-muted-foreground/70 hover:bg-muted hover:text-foreground"
            }`}
          >
            <Trash2 className="h-2.5 w-2.5" />
            {confirmClear ? "confirm?" : "clear all"}
          </button>
        )}
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
          const isEditing = editingId === s.id;
          return (
            <div
              key={s.id}
              onClick={() => !isEditing && onSelect(s.id)}
              className={`group flex w-full cursor-pointer items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors ${
                active
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-transparent hover:border-border hover:bg-muted/40"
              }`}
            >
              <div
                className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                  active ? "bg-emerald-400" : "bg-muted-foreground/40"
                }`}
              />
              <div className="min-w-0 flex-1">
                {isEditing ? (
                  <div className="flex items-center gap-1">
                    <input
                      ref={editRef}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(s.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="w-full rounded border border-emerald-500/50 bg-input px-1.5 py-0.5 text-xs text-foreground focus:outline-none"
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        commitRename(s.id);
                      }}
                      className="rounded p-0.5 text-emerald-400 hover:bg-emerald-500/20"
                    >
                      <Check className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <div
                    className={`truncate text-xs font-medium ${
                      active ? "text-emerald-200" : "text-foreground/90"
                    }`}
                  >
                    {s.title}
                  </div>
                )}
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <span>{relativeTime(s.updatedAt)}</span>
                  <span>·</span>
                  <span>{s.messageCount} msg</span>
                </div>
              </div>
              {!isEditing && (
                <div className="mt-0.5 flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    onClick={(e) => exportSession(s.id, e)}
                    className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-emerald-300"
                    aria-label="export session"
                    title="export as markdown"
                  >
                    <Download className="h-3 w-3" />
                  </button>
                  <button
                    onClick={(e) => startRename(s, e)}
                    className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-sky-300"
                    aria-label="rename session"
                    title="rename"
                  >
                    <Edit3 className="h-3 w-3" />
                  </button>
                  <button
                    onClick={(e) => remove(s.id, e)}
                    className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-red-400"
                    aria-label="delete session"
                    title="delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* footer with stats */}
      <div className="border-t border-border px-3 py-2.5">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Plus className="h-3 w-3" />
          <span>by {NEXA_AUTHOR}</span>
        </div>
        <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground/60">
          <span>MIT License · © 2026</span>
          <span className="font-mono">{totalMsgs} msg total</span>
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
