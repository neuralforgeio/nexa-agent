/**
 * Nexa Agent — Sidebar (Z.ai minimal + full CRUD + pin/archive + search)
 * ==================================================
 *
 * - Logo header + New Chat pill
 * - Session history grouped by time (Today / Yesterday / Older)
 * - F-03: search box (queries the backend's FTS5 search via ?q=)
 * - F-04: pin / archive per session; pinned float to the top, archived
 *   collapse into a "Archived" section; date grouping preserved
 * - F-12: per-session export (Markdown / JSON) download button
 * - Rename (double-click or pencil) + delete (two-click confirm)
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
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
  Search,
  Pin,
  PinOff,
  Archive,
  ArchiveRestore,
  Download,
} from "lucide-react";
import type { Session } from "../lib/theme";
import { groupByDate, splitByPinArchive } from "../lib/sessions";
import { SettingsPanel } from "./SettingsPanel";

const GROUPS = ["Today", "Yesterday", "Older"] as const;

interface SidebarProps {
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
}

export function Sidebar({ activeSessionId, onSelect, onNew, refreshKey }: SidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  // F-03: search box
  const [query, setQuery] = useState("");
  // F-04: show the archived section
  const [showArchived, setShowArchived] = useState(false);

  const searching = query.trim().length > 0;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        // Always fetch with includeArchived so the client can split the
        // buckets itself; `q` is forwarded to the backend FTS search (F-03).
        const url =
          "/api/sessions?includeArchived=true" +
          (query.trim() ? `&q=${encodeURIComponent(query.trim())}` : "");
        const res = await fetch(url, { cache: "no-store" });
        const data = await res.json();
        if (!cancelled) setSessions(data.sessions ?? []);
      } catch {
        /* keep previous list */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey, query]);

  // F-04: split into pinned / normal (date-grouped) / archived.
  const { pinned, normal, archived } = useMemo(
    () => splitByPinArchive(sessions),
    [sessions]
  );
  const groupedNormal = useMemo(() => groupByDate(normal), [normal]);

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (deletingId !== id) {
      setDeletingId(id);
      window.setTimeout(() => {
        setDeletingId((cur) => (cur === id ? null : cur));
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
    setRenamingId(null);
    if (!next) return;
    const ok = await patchFlags(id, { title: next });
    if (ok) setSessions((all) => all.map((s) => (s.id === id ? { ...s, title: next } : s)));
  };

  // F-04: toggle pin / archive with an optimistic UI update.
  const togglePin = async (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !s.pinned;
    await patchFlags(s.id, { pinned: next });
    setSessions((all) => all.map((x) => (x.id === s.id ? { ...x, pinned: next } : x)));
  };
  const toggleArchive = async (s: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = !s.archived;
    await patchFlags(s.id, { archived: next });
    setSessions((all) => all.map((x) => (x.id === s.id ? { ...x, archived: next } : x)));
  };

  // F-12: download a session transcript via the existing export endpoint.
  const exportSession = (s: Session, format: "md" | "json", e: React.MouseEvent) => {
    e.stopPropagation();
    const a = document.createElement("a");
    a.href = `/api/export/${s.id}?format=${format}`;
    a.download = `${(s.title || "session").replace(/[^\w.-]+/g, "_").slice(0, 60)}.${format === "md" ? "md" : "json"}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  async function patchFlags(
    id: string,
    patch: { title?: string; pinned?: boolean; archived?: boolean }
  ): Promise<boolean> {
    try {
      const res = await fetch(`/api/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

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
        {/* Pin indicator */}
        {s.pinned ? (
          <Pin size={12} color="#4A9EFF" style={{ flexShrink: 0 }} />
        ) : (
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: isActive ? "#4A9EFF" : "#2E2F34",
              flexShrink: 0,
            }}
          />
        )}

        {/* Title (or rename input) */}
        {isRenaming ? (
          <input
            autoFocus
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Enter") void commitRename(s.id);
              if (e.key === "Escape") setRenamingId(null);
            }}
            onBlur={() => void commitRename(s.id)}
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

        {/* Hover actions */}
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
            <button onClick={(e) => void togglePin(s, e)} title={s.pinned ? "Unpin" : "Pin"} style={iconBtn}>
              {s.pinned ? <PinOff size={13} color="#4A9EFF" /> : <Pin size={13} color="#8F8F8F" />}
            </button>
            <button
              onClick={(e) => exportSession(s, "md", e)}
              title="Export as Markdown"
              style={iconBtn}
            >
              <Download size={13} color="#8F8F8F" />
            </button>
            <button
              onClick={(e) => void toggleArchive(s, e)}
              title={s.archived ? "Unarchive" : "Archive"}
              style={iconBtn}
            >
              {s.archived ? <ArchiveRestore size={13} color="#8F8F8F" /> : <Archive size={13} color="#8F8F8F" />}
            </button>
            <button onClick={(e) => startRename(s, e)} title="Rename session" style={iconBtn}>
              <Pencil size={13} color="#8F8F8F" />
            </button>
            <button
              onClick={(e) => void remove(s.id, e)}
              title={isDeleting ? "Click again to delete" : "Delete session"}
              style={{ ...iconBtn, ...(isDeleting ? { background: "rgba(248,113,113,0.12)" } : {}) }}
            >
              <Trash2 size={13} color={isDeleting ? "#F87171" : "#8F8F8F"} />
            </button>
          </div>
        )}
        {isRenaming && (
          <button onClick={() => void commitRename(s.id)} style={iconBtn} title="Save">
            <Check size={13} color="#4ADE80" />
          </button>
        )}
      </div>
    );
  };

  const renderSection = (label: string, list: Session[]) =>
    list.length === 0 ? null : (
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

      {/* F-03: search box */}
      <div style={{ padding: "0 12px 8px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "#0D0E10",
            border: "1px solid #24262B",
            borderRadius: 8,
            padding: "6px 10px",
          }}
        >
          <Search size={13} color="#6A6A6A" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations…"
            aria-label="search-sessions"
            style={{
              flex: 1,
              minWidth: 0,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#ECECEC",
              fontSize: 13,
            }}
          />
          {query && (
            <button onClick={() => setQuery("")} aria-label="clear-search" style={iconBtn} title="Clear search">
              <X size={12} color="#8F8F8F" />
            </button>
          )}
        </div>
      </div>

      {/* Session list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px" }}>
        {loading ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
            Loading…
          </div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
            {searching ? "No conversations match your search." : "No conversations yet."}
          </div>
        ) : (
          <>
            {/* Pinned (F-04) — only meaningful when not searching */}
            {!searching && pinned.length > 0 && renderSection("Pinned", pinned)}

            {/* Normal, date-grouped (F-04). When searching we show a flat list. */}
            {searching
              ? renderSection("Results", normal)
              : GROUPS.map((label) => renderSection(label, groupedNormal[label]))}

            {/* Archived (F-04) */}
            {archived.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => setShowArchived((v) => !v)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background: "transparent",
                    border: "none",
                    color: "#6A6A6A",
                    fontSize: 10,
                    textTransform: "uppercase",
                    letterSpacing: 1.2,
                    fontWeight: 700,
                    padding: "8px 12px 4px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Archive size={11} /> Archived ({archived.length}) {showArchived ? "▾" : "▸"}
                </button>
                {showArchived && archived.map(renderRow)}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid #1e2023", padding: "10px 14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
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
      <button onClick={onExpand} title="Expand sidebar" style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0, marginBottom: 6 }}>
        <img src="/nexa-agent.png" alt="Nexa" style={{ width: 28, height: 28, borderRadius: 8, objectFit: "cover" }} />
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
