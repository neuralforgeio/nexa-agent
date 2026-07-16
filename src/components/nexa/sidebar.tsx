"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  Download,
  Edit3,
  MessageSquarePlus,
  Search,
  Trash2,
  X,
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
  const [search, setSearch] = useState("");
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
    setSessions((s) => s.map((x) => (x.id === id ? { ...x, title } : x)));
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
      sessions.map((s) => fetch(`/api/sessions/${s.id}`, { method: "DELETE" }))
    );
    setSessions([]);
    setConfirmClear(false);
    onSelect("");
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, search]);

  const grouped = useMemo(() => groupByDate(filtered), [filtered]);
  const totalMsgs = sessions.reduce((a, s) => a + s.messageCount, 0);

  return (
    <aside className="flex h-full w-full flex-col bg-sidebar">
      {/* Brand header */}
      <div className="flex items-center gap-2.5 px-3 py-3">
        <div className="relative h-8 w-8 overflow-hidden rounded-lg">
          <img
            src="/nexa-agent.png"
            alt="Nexa Agent"
            className="h-full w-full object-cover"
          />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[15px] font-semibold tracking-tight text-foreground">
              Nexa Agent
            </span>
            <span className="rounded bg-accent px-1 py-px text-[9px] font-semibold text-primary">
              v{NEXA_VERSION}
            </span>
          </div>
          <div className="text-[11px] text-secondary">AI agent runtime</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto rounded-md p-1.5 text-secondary hover:bg-tertiary hover:text-foreground lg:hidden"
            aria-label="close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* New chat */}
      <div className="px-2.5 pb-2">
        <button
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2.5 text-[13px] font-medium text-primary-foreground transition-colors hover:bg-accent-hover"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New chat
        </button>
      </div>

      {/* Search */}
      <div className="px-2.5 pb-2">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-tertiary px-2.5 py-1.5">
          <Search className="h-3.5 w-3.5 text-tertiary" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full bg-transparent text-[13px] text-foreground placeholder:text-tertiary focus:outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="text-tertiary hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto nexa-scroll px-1.5 pb-2">
        {loading && (
          <div className="space-y-1.5 px-1 py-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-tertiary/50" />
            ))}
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="px-3 py-8 text-center">
            <p className="text-[13px] text-tertiary">
              {search ? "No conversations found" : "No conversations yet"}
            </p>
            {!search && (
              <p className="mt-1 text-[12px] text-tertiary">
                Start a new chat to begin
              </p>
            )}
          </div>
        )}
        {grouped.map((group) => (
          <div key={group.label} className="mb-1">
            <div className="px-2 py-1.5 text-[11px] font-medium uppercase tracking-wide text-tertiary">
              {group.label}
            </div>
            {group.items.map((s) => {
              const active = s.id === activeId;
              const isEditing = editingId === s.id;
              return (
                <div
                  key={s.id}
                  onClick={() => !isEditing && onSelect(s.id)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors ${
                    active ? "bg-tertiary" : "hover:bg-tertiary/60"
                  }`}
                >
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
                          className="w-full rounded border border-primary bg-elevated px-1.5 py-0.5 text-[13px] text-foreground focus:outline-none"
                        />
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            commitRename(s.id);
                          }}
                          className="rounded p-0.5 text-primary hover:bg-accent"
                        >
                          <Check className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <div
                        className={`truncate text-[13px] ${
                          active ? "text-foreground font-medium" : "text-foreground/90"
                        }`}
                      >
                        {s.title}
                      </div>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={(e) => exportSession(s.id, e)}
                        className="rounded p-1 text-tertiary hover:bg-elevated hover:text-primary"
                        aria-label="export"
                        title="Export as markdown"
                      >
                        <Download className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={(e) => startRename(s, e)}
                        className="rounded p-1 text-tertiary hover:bg-elevated hover:text-primary"
                        aria-label="rename"
                        title="Rename"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={(e) => remove(s.id, e)}
                        className="rounded p-1 text-tertiary hover:bg-elevated hover:text-error"
                        aria-label="delete"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-3 py-2.5">
        <div className="flex items-center justify-between">
          <div className="text-[11px] text-tertiary">© 2026 {NEXA_AUTHOR}</div>
          {sessions.length > 0 && (
            <button
              onClick={clearAll}
              className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] transition-colors ${
                confirmClear
                  ? "bg-error/15 text-error"
                  : "text-tertiary hover:bg-tertiary hover:text-foreground"
              }`}
            >
              <Trash2 className="h-2.5 w-2.5" />
              {confirmClear ? "Confirm?" : `Clear all (${totalMsgs})`}
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

interface DateGroup {
  label: string;
  items: SessionItem[];
}

function groupByDate(sessions: SessionItem[]): DateGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, SessionItem[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 Days": [],
    Older: [],
  };

  for (const s of sessions) {
    const d = new Date(s.updatedAt);
    if (d >= today) groups["Today"].push(s);
    else if (d >= yesterday) groups["Yesterday"].push(s);
    else if (d >= weekAgo) groups["Previous 7 Days"].push(s);
    else groups["Older"].push(s);
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}
