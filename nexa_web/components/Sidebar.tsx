/**
 * Nexa Agent — Sidebar (Z.ai minimal + full CRUD)
 * ==================================================
 *
 * Minimalist sidebar with:
 *  - Logo header
 *  - New Chat pill button
 *  - Session history grouped by time (Today / Yesterday / Older)
 *  - Per-session rename (double-click or pencil) + delete (trash icon)
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MessageSquarePlus,
  Pencil,
  Trash2,
  Settings as SettingsIcon,
  Check,
  X,
} from "lucide-react";
import type { Session } from "../lib/theme";
import { SettingsPanel } from "./SettingsPanel";

interface SidebarProps {
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
  /** When true, renders the slim icon-only variant (Z.ai style, ~64px wide). */
  collapsed?: boolean;
}

type SessionGroup = "Today" | "Yesterday" | "Older";

function groupLabel(iso: string): SessionGroup {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "Older";
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const thatMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const days = Math.round((midnight.getTime() - thatMidnight.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return "Older";
}

export function Sidebar({ activeSessionId, onSelect, onNew, refreshKey }: SidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch("/api/sessions", { cache: "no-store" });
        const data = await res.json();
        if (!cancelled) setSessions(data.sessions ?? []);
      } catch {
        /* keep */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const grouped = useMemo(() => {
    const buckets: Record<SessionGroup, Session[]> = {
      Today: [],
      Yesterday: [],
      Older: [],
    };
    for (const s of sessions) buckets[groupLabel(s.updatedAt)].push(s);
    return buckets;
  }, [sessions]);

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    // Two-phase delete: first click marks the row, second click confirms.
    if (deletingId !== id) {
      setDeletingId(id);
      // Auto-cancel after 3 s if not confirmed.
      window.setTimeout(() => {
        setDeletingId((current) => (current === id ? null : current));
      }, 3000);
      return;
    }
    try {
      await fetch(`/api/sessions/${id}`, { method: "DELETE" });
      setSessions((s) => s.filter((x) => x.id !== id));
      setDeletingId(null);
      if (activeSessionId === id) onSelect("");
    } catch {
      setDeletingId(null);
    }
  };

  const startRename = (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingId(s.id);
    setRenameValue(s.title);
  };

  const commitRename = async (id: string) => {
    const next = renameValue.trim();
    if (!next) {
      setRenamingId(null);
      return;
    }
    try {
      const res = await fetch(`/api/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: next }),
      });
      if (res.ok) {
        setSessions((all) => all.map((s) => (s.id === id ? { ...s, title: next } : s)));
      }
    } finally {
      setRenamingId(null);
    }
  };

  const renderRow = (s: Session) => {
    const isActive = activeSessionId === s.id;
    const isRenaming = renamingId === s.id;
    const isDeleting = deletingId === s.id;

    return (
      <div
        key={s.id}
        onClick={() => !isRenaming && onSelect(s.id)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 12px",
          borderRadius: 8,
          marginBottom: 2,
          cursor: isRenaming ? "default" : "pointer",
          background: isActive ? "rgba(74, 158, 255, 0.12)" : "transparent",
          border: isActive ? "1px solid rgba(74, 158, 255, 0.25)" : "1px solid transparent",
          transition: "background 0.15s, border 0.15s",
          position: "relative",
        }}
        onMouseEnter={(e) => {
          if (!isActive && !isRenaming) e.currentTarget.style.background = "var(--nexa-panel-2, #1A1B1E)";
        }}
        onMouseLeave={(e) => {
          if (!isActive && !isRenaming) e.currentTarget.style.background = "transparent";
        }}
      >
        {/* Activity dot */}
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: isActive ? "#4A9EFF" : "#2E2F34",
            flexShrink: 0,
          }}
        />

        {/* Title (or rename input) */}
        {isRenaming ? (
          <input
            autoFocus
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename(s.id);
              if (e.key === "Escape") setRenamingId(null);
            }}
            onBlur={() => commitRename(s.id)}
            style={{
              flex: 1,
              minWidth: 0,
              background: "#0D0E10",
              border: "1px solid rgba(74, 158, 255, 0.4)",
              borderRadius: 6,
              padding: "4px 8px",
              color: "#ECECEC",
              fontSize: 13,
              outline: "none",
            }}
          />
        ) : (
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "#4A9EFF" : "#ECECEC",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={s.title}
            >
              {s.title}
            </div>
            <div style={{ fontSize: 11, color: "#6A6A6A" }}>{s.messageCount} msg</div>
          </div>
        )}

        {/* Action buttons (visible on hover / when renaming) */}
        {!isRenaming && (
          <div
            style={{
              display: "flex",
              gap: 2,
              opacity: isActive || isDeleting ? 1 : 0,
              transition: "opacity 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
          >
            <button
              onClick={(e) => startRename(s, e)}
              title="Rename session"
              style={iconBtn}
            >
              <Pencil size={13} color="#8F8F8F" />
            </button>
            <button
              onClick={(e) => remove(s.id, e)}
              title={isDeleting ? "Click again to delete" : "Delete session"}
              style={{ ...iconBtn, ...(isDeleting ? { background: "rgba(248,113,113,0.12)" } : {}) }}
            >
              <Trash2 size={13} color={isDeleting ? "#F87171" : "#8F8F8F"} />
            </button>
          </div>
        )}
        {isRenaming && (
          <button onClick={() => commitRename(s.id)} style={iconBtn} title="Save">
            <Check size={13} color="#4ADE80" />
          </button>
        )}
      </div>
    );
  };

  return (
    <aside
      style={{
        width: 264,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        background: "#141618",
        borderRight: "1px solid #24262B",
        height: "100%",
      }}
    >
      {/* Logo header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 14px 10px",
          borderBottom: "1px solid #1e2023",
        }}
      >
        <img
          src="/nexa-agent.png"
          alt="Nexa"
          style={{ width: 32, height: 32, borderRadius: 8, objectFit: "cover" }}
        />
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#ECECEC", letterSpacing: -0.2 }}>
            Nexa Agent
          </div>
          <div style={{ fontSize: 11, color: "#6A6A6A" }}>Chat = Agent</div>
        </div>
      </div>

      {/* New Chat */}
      <div style={{ padding: "12px 12px 8px" }}>
        <button
          onClick={onNew}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "10px 16px",
            borderRadius: 8,
            border: "1px solid rgba(74,158,255,0.3)",
            background: "rgba(74,158,255,0.10)",
            color: "#4A9EFF",
            fontSize: 13.5,
            fontWeight: 600,
            cursor: "pointer",
            transition: "background 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(74,158,255,0.18)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(74,158,255,0.10)")}
        >
          <MessageSquarePlus size={16} />
          New Chat
        </button>
      </div>

      {/* Session list grouped by time */}
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px" }}>
        {loading ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
            Loading…
          </div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
            No conversations yet.
          </div>
        ) : (
          (["Today", "Yesterday", "Older"] as const).map((label) => {
            const list = grouped[label];
            if (list.length === 0) return null;
            return (
              <div key={label} style={{ marginBottom: 12 }}>
                <div
                  style={{
                    fontSize: 10,
                    color: "#6A6A6A",
                    textTransform: "uppercase",
                    letterSpacing: 1.2,
                    padding: "8px 12px 4px",
                    fontWeight: 700,
                  }}
                >
                  {label}
                </div>
                {list.map(renderRow)}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid #1e2023",
          padding: "10px 14px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 10, color: "#6A6A6A" }}>© 2026 Dearly Febriano Irwansyah</div>
            <div style={{ fontSize: 10, color: "#6A6A6A" }}>MIT License</div>
          </div>
          <button
            onClick={() => setShowSettings(true)}
            aria-label="Provider settings"
            title="Manage LLM providers"
            style={{
              background: "transparent",
              border: "1px solid #2a2c30",
              color: "#9A9A9A",
              cursor: "pointer",
              padding: "6px 10px",
              borderRadius: 6,
              fontSize: 11,
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <SettingsIcon size={12} />
            Providers
          </button>
        </div>
      </div>

      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
    </aside>
  );
}

export function CollapsedSidebar({ onNew, onExpand }: { onNew: () => void; onExpand: () => void }) {
  /**
   * Icon-only sidebar (Z.ai super-mini, image #4 style).
   * ~52px wide; exposes Logo + New-Chat + Expand button.
   */
  return (
    <aside
      style={{
        width: 52,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        padding: "12px 0",
        background: "#0B0C0E",
        borderRight: "1px solid #1e2023",
        height: "100%",
      }}
    >
      <button
        onClick={onExpand}
        title="Expand sidebar"
        style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0, marginBottom: 6 }}
      >
        <img
          src="/nexa-agent.png"
          alt="Nexa"
          style={{ width: 28, height: 28, borderRadius: 8, objectFit: "cover" }}
        />
      </button>
      <button
        onClick={onNew}
        title="New chat"
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: "rgba(74,158,255,0.10)",
          border: "1px solid rgba(74,158,255,0.3)",
          color: "#4A9EFF",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <MessageSquarePlus size={16} />
      </button>
    </aside>
  );
}

const iconBtn: React.CSSProperties = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  padding: "4px 6px",
  borderRadius: 5,
  display: "flex",
  alignItems: "center",
};
