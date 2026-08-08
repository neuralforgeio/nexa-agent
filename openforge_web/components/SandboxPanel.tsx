/**
 * Nexa Agent — Sandbox Panel (v4.1.0)
 *
 * Right-side panel with vertically split Preview + Terminal.
 * - Preview (top): iframe for built web projects (auto-served via /workspace-preview)
 * - Terminal (bottom): real PTY via xterm.js + WebSocket
 * - Draggable divider: resize either panel; double-click to collapse
 * - Can be fully closed; remembers split position in localStorage
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { X, Globe, Terminal as TerminalIcon, GripHorizontal, RefreshCw } from "lucide-react";

const TerminalPanel = dynamic(
  () => import("./TerminalPanel").then((m) => m.TerminalPanel),
  { ssr: false }
);

interface SandboxPanelProps {
  onClose: () => void;
  width: number;
}

const STORAGE_KEY = "nexa-sandbox-split";

// If a dev server is detected we prefer that live preview; otherwise the
// sandbox falls back to Nexa's /api/sandbox/preview (static file serving
// from the workspace). This lets a plain HTML/CSS/JS project render
// immediately — no build step needed.
const DEV_SERVER_CANDIDATES = [
  "http://localhost:3000",
  "http://localhost:5173",
  "http://localhost:4321",
  "http://localhost:4200",
  "http://localhost:8080",
];

export function SandboxPanel({ onClose, width }: SandboxPanelProps) {
  const [tab, setTab] = useState<"split" | "preview" | "terminal">("split");
  const [split, setSplit] = useState(50); // % for preview
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [workspacePath, setWorkspacePath] = useState<string>(""); // manual override
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load saved split
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setSplit(Number(saved));
  }, []);

  // Try to detect a running preview server in the workspace.
  // IMPORTANT: skip Nexa's own dev port (3000) — that would just render the
  // agent's own UI inside its own panel (the "recursive iframe" bug).
  const detectPreview = useCallback(async () => {
    // Manual override: a workspace-relative path to render via
    // /api/sandbox/preview — wins over dev-server autodetect.
    if (workspacePath) {
      const encoded = encodeURIComponent(workspacePath);
      const url = `/api/sandbox/preview?path=${encoded}`;
      setPreviewUrl(url);
      return url;
    }
    // Filter out Nexa's own UI (port 3000) and the llama.cpp router port.
    const skip = new Set(["http://localhost:3000", "http://localhost:8080"]);
    for (const url of DEV_SERVER_CANDIDATES) {
      if (skip.has(url)) continue;
      try {
        await fetch(url, { mode: "no-cors", signal: AbortSignal.timeout(800) });
        // no-cors resolves even on opaque responses; assume reachable
        setPreviewUrl(url);
        return url;
      } catch { /* not reachable */ }
    }
    setPreviewUrl(null);
    return null;
  }, [workspacePath]);

  useEffect(() => {
    detectPreview();
    const iv = setInterval(detectPreview, 10000);
    return () => clearInterval(iv);
  }, [detectPreview, workspacePath]);

  // Drag logic
  const onMouseDown = useCallback(() => setDragging(true), []);
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const pct = ((e.clientY - rect.top) / rect.height) * 100;
      const clamped = Math.min(85, Math.max(15, pct));
      setSplit(clamped);
      localStorage.setItem(STORAGE_KEY, String(clamped));
    };
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

  const showPreview = tab !== "terminal";
  const showTerminal = tab !== "preview";

  return (
    <aside
      style={{
        width,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#0D0E10",
        borderLeft: "1px solid #24262B",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "8px 10px",
          borderBottom: "1px solid #24262B",
          background: "#141618",
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 700, color: "#9A9A9A", marginRight: "auto", letterSpacing: 1 }}>
          SANDBOX
        </span>
        <TabButton active={tab === "split"} onClick={() => setTab("split")} title="Split view">
          <span style={{ fontSize: 11 }}>50/50</span>
        </TabButton>
        <TabButton active={tab === "preview"} onClick={() => setTab("preview")} title="Preview only">
          <Globe size={13} />
        </TabButton>
        <TabButton active={tab === "terminal"} onClick={() => setTab("terminal")} title="Terminal only">
          <TerminalIcon size={13} />
        </TabButton>
        <button
          onClick={onClose}
          title="Close sandbox"
          style={{ background: "none", border: "none", color: "#9A9A9A", cursor: "pointer", padding: 4, borderRadius: 6 }}
        >
          <X size={15} />
        </button>
      </div>

      {/* Body */}
      <div ref={containerRef} style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, position: "relative" }}>
        {/* Preview pane */}
        {showPreview && (
          <div
            style={{
              height: showTerminal && tab === "split" ? `${split}%` : "100%",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              background: "#fff",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 8px",
                background: "#1A1B1E",
                borderBottom: "1px solid #24262B",
              }}
            >
              <Globe size={12} color="#4A9EFF" />
              <span style={{ fontSize: 11, color: "#9A9A9A", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {previewUrl ?? "No preview detected — run a dev server"}
              </span>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const fd = new FormData(e.currentTarget);
                  const p = (fd.get("wp") as string | null)?.trim();
                  setWorkspacePath(p || "");
                }}
                style={{ display: "flex", alignItems: "center", gap: 4 }}
              >
                <input
                  name="wp"
                  placeholder="workspace path…"
                  defaultValue={workspacePath}
                  key={workspacePath}
                  aria-label="Workspace path to preview"
                  style={{
                    width: 130,
                    background: "#0D0E10",
                    border: "1px solid #24262B",
                    borderRadius: 4,
                    padding: "2px 7px",
                    color: "#ECECEC",
                    fontSize: 11,
                    outline: "none",
                  }}
                />
              </form>
              {workspacePath && (
                <button
                  onClick={() => setWorkspacePath("")}
                  title="Back to dev-server autodetect"
                  style={{ background: "none", border: "none", color: "#6A6A6A", cursor: "pointer", padding: 2, fontSize: 10 }}
                >
                  auto
                </button>
              )}
              <button
                onClick={() => {
                  setPreviewUrl(null);
                  detectPreview();
                  const frame = document.getElementById("sandbox-frame") as HTMLIFrameElement | null;
                  if (frame && previewUrl) frame.src = previewUrl;
                }}
                title="Refresh preview"
                style={{ background: "none", border: "none", color: "#9A9A9A", cursor: "pointer", padding: 2 }}
              >
                <RefreshCw size={12} />
              </button>
            </div>
            {previewUrl ? (
              <iframe
                id="sandbox-frame"
                src={previewUrl}
                style={{ flex: 1, border: "none", width: "100%" }}
                title="Project preview"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              />
            ) : (
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "#0D0E10",
                  color: "#6A6A6A",
                  fontSize: 13,
                  gap: 8,
                  padding: 20,
                  textAlign: "center",
                }}
              >
                <Globe size={28} style={{ opacity: 0.3 }} />
                <span>
                  Ask Nexa to build a web project — the preview appears here automatically when a dev server starts.
                </span>
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        {tab === "split" && showPreview && showTerminal && (
          <div
            onMouseDown={onMouseDown}
            onDoubleClick={() => {
              setSplit(50);
              localStorage.setItem(STORAGE_KEY, "50");
            }}
            style={{
              height: 8,
              cursor: "row-resize",
              background: dragging ? "rgba(74,158,255,0.3)" : "#141618",
              borderTop: "1px solid #24262B",
              borderBottom: "1px solid #24262B",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "background 0.15s",
            }}
            title="Drag to resize, double-click to reset"
          >
            <GripHorizontal size={12} color="#6A6A6A" />
          </div>
        )}

        {/* Terminal pane */}
        {showTerminal && (
          <div
            style={{
              height: showPreview && tab === "split" ? `${100 - split}%` : "100%",
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <TerminalPanel onClose={() => setTab("preview")} embedded />
          </div>
        )}
      </div>
    </aside>
  );
}

function TabButton({
  active,
  onClick,
  title,
  children,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: active ? "rgba(74,158,255,0.15)" : "transparent",
        border: active ? "1px solid rgba(74,158,255,0.4)" : "1px solid transparent",
        color: active ? "#4A9EFF" : "#9A9A9A",
        cursor: "pointer",
        padding: "4px 7px",
        borderRadius: 6,
        display: "flex",
        alignItems: "center",
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}
