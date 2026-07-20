/**
 * Nexa Agent — Sidebar Component
 *
 * Minimalist sidebar with logo, New Chat button, session history.
 */

"use client";

import { useEffect, useState } from "react";
import { MessageSquarePlus, Trash2, Zap } from "lucide-react";
import type { Session } from "../lib/theme";

interface SidebarProps {
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
}

export function Sidebar({ activeSessionId, onSelect, onNew, refreshKey }: SidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch("/api/sessions", { cache: "no-store" });
        const data = await res.json();
        if (!cancelled) setSessions(data.sessions ?? []);
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey]);

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    setSessions((s) => s.filter((x) => x.id !== id));
    if (activeSessionId === id) onSelect("");
  };

  return (
    <aside style={{
      width: 260, flexShrink: 0, display: "flex", flexDirection: "column",
      background: "#1A1B1E", borderRight: "1px solid #2E2F34", height: "100%",
    }}>
      {/* Logo header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 16px" }}>
        <img src="/nexa-agent.png" alt="Nexa" style={{ width: 32, height: 32, borderRadius: 8, objectFit: "cover" }} />
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#ECECEC" }}>Nexa Agent</div>
          <div style={{ fontSize: 11, color: "#6A6A6A" }}>Chat = Agent</div>
        </div>
      </div>

      {/* New Chat */}
      <div style={{ padding: "0 12px 12px" }}>
        <button
          onClick={onNew}
          style={{
            width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            padding: "10px 16px", borderRadius: 8, border: "1px solid #2E2F34",
            background: "#222327", color: "#ECECEC", fontSize: 14, fontWeight: 500,
            cursor: "pointer", transition: "all 0.2s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#2A2B30"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "#222327"; }}
        >
          <MessageSquarePlus size={18} />
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 8px" }}>
        {loading ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>Loading…</div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
            No conversations yet.
          </div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => onSelect(s.id)}
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "10px 12px",
                borderRadius: 8, marginBottom: 2, cursor: "pointer",
                background: activeSessionId === s.id ? "rgba(74, 158, 255, 0.12)" : "transparent",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => { if (activeSessionId !== s.id) e.currentTarget.style.background = "#222327"; }}
              onMouseLeave={(e) => { if (activeSessionId !== s.id) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{
                width: 6, height: 6, borderRadius: "50%",
                background: activeSessionId === s.id ? "#4A9EFF" : "#2E2F34", flexShrink: 0,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 13, fontWeight: activeSessionId === s.id ? 500 : 400,
                  color: activeSessionId === s.id ? "#4A9EFF" : "#ECECEC",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>
                  {s.title}
                </div>
                <div style={{ fontSize: 11, color: "#6A6A6A" }}>{s.messageCount} msg</div>
              </div>
              <button
                onClick={(e) => remove(s.id, e)}
                style={{ opacity: 0, transition: "opacity 0.15s", background: "none", border: "none", cursor: "pointer", padding: 4 }}
                onMouseEnter={(e) => { e.currentTarget.parentElement!.style.opacity = "1"; }}
              >
                <Trash2 size={14} color="#6A6A6A" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid #2E2F34", padding: "12px 16px" }}>
        <div style={{ fontSize: 11, color: "#6A6A6A" }}>© 2026 Dearly Febriano Irwansyah</div>
        <div style={{ fontSize: 11, color: "#6A6A6A" }}>MIT License</div>
      </div>
    </aside>
  );
}
