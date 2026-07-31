/**
 * Nexa Agent — Terminal Panel (v3.2.0 — xterm.js real PTY)
 * ==========================================================
 *
 * A real terminal in the browser, powered by xterm.js and a WebSocket
 * PTY backend. The AI can invoke `open_terminal_panel` + `terminal_exec`
 * tools to control the user's shell in real-time.
 *
 * Features:
 *   - ANSI color support (256-color + true color)
 *   - Escape sequence support (cursor movement, clear, etc.)
 *   - Resizable panel (colorcoded 40% default, collapsible)
 *   - WebSocket connection with auto-reconnect
 *   - tool calls: AI can open terminal + run commands + read output
 *   - Unicode safe (UTF-8)
 *
 * Backend: server.py's `/ws/terminal` WebSocket with real PTY
 * (ptyprocess on Unix, winpty on Windows).
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import * as icons from "lucide-react";

interface TerminalPanelProps {
  onClose?: () => void;
  isVisible?: boolean;
  onToggle?: (visible: boolean) => void;
  /** When true, renders as a flex-fill panel (embedded) instead of a fixed bottom overlay. */
  embedded?: boolean;
  /**
   * Workspace-relative directory for the shell's starting cwd.
   * Defaults to the workspace root.
   */
  cwd?: string;
}

export function TerminalPanel({ onClose, isVisible = true, onToggle, embedded = false, cwd = "" }: TerminalPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [height, setHeight] = useState(320); // px

  // Initialize xterm.js when mounted. Runs exactly once per component
  // instance (``initializedRef`` guards against React 18 StrictMode's
  // double-invocation in dev).
  useEffect(() => {
    if (!containerRef.current) return;
    if (termRef.current) {
      // Already initialized (StrictMode re-run) — skip.
      return;
    }

    const term = new XTerm({
      cursorBlink: true,
      cursorStyle: "block",
      fontFamily: "JetBrains Mono, 'Fira Code', monospace",
      fontSize: 13,
      fontWeight: "normal",
      letterSpacing: 0,
      lineHeight: 1.2,
      // Dark theme matching our app.
      theme: {
        background: "#0F0F0F",
        foreground: "#ECECEC",
        cursor: "#4A9EFF",
        cursorAccent: "#0F0F0F",
        selectionBackground: "#2E2F34",
        black: "#0F0F0F",
        red: "#F87171",
        green: "#4ADE80",
        yellow: "#FBBF24",
        blue: "#4A9EFF",
        magenta: "#C084FC",
        cyan: "#22D3EE",
        white: "#ECECEC",
        brightBlack: "#6A6A6A",
        brightRed: "#FCA5A5",
        brightGreen: "#86EFAC",
        brightYellow: "#FDE047",
        brightBlue: "#93C5FD",
        brightMagenta: "#E9D5FF",
        brightCyan: "#67E8F9",
        brightWhite: "#F9FAFB",
      },
      allowProposedApi: true,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);

    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitRef.current = fitAddon;

    // Write welcome message — ASCII ONLY.
    // (The previous banner used UTF-8 box-drawing chars that render as
    //  "repeated Y" glyphs in some xterm.js+Turbopack font setups. ASCII
    //  works everywhere: Windows Terminal, PowerShell, Git Bash, WSL, etc.)
    term.writeln("+----------------------------------------------------------+");
    term.writeln("|  NEXA TERMINAL — real PTY shell (xterm.js)                |");
    term.writeln("|  Starts in your NEXA workspace. Try `dir` or `ls`.        |");
    term.writeln("|  Shortcuts: 'clear' to reset, 'exit' to close.            |");
    term.writeln("+----------------------------------------------------------+");
    term.writeln("");

    // Handle user input → send to WebSocket PTY.
    term.onData((data) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Connect WebSocket.
    connectWebSocketRef.current?.(term);

    // Handle resize.
    const container = containerRef.current;
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(container);

    return () => {
      if (reconnectTimerRef.current != null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      resizeObserver.disconnect();
      wsRef.current?.close();
      wsRef.current = null;
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
    // Note: this effect intentionally runs only once per mount.
  }, []);

  // Connect to the backend PTY WebSocket. Defined AFTER the mount effect so
  // the circular-reference eslint rule can't fire; the ref indirection lets
  // the effect call it even though it runs earlier in the source.
  const connectWebSocketRef = useRef<((t: XTerm) => void) | null>(null);

  const connectWebSocket = useCallback((term: XTerm): void => {
    // Connect DIRECTLY to the Python backend (port 8000). Next.js App Router
    // has no WebSocket upgrade proxy, so we must not route through
    // ``/api/...`` rewrites — those only handle plain HTTP.
    const backendWsUrl =
      (process.env.NEXT_PUBLIC_NEXA_WS as string | undefined) ??
      "ws://127.0.0.1:8000/ws/terminal";
    const ws = new WebSocket(backendWsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
      reconnectAttemptRef.current = 0;
      term.writeln("\x1b[32m[connected]\x1b[0m Nexa PTY session established.");
      // Send initial PTY size. The shell was already spawned with the
      // workspace root as cwd by the backend; the user can `cd` anywhere
      // inside the workspace from here.
      if (fitRef.current) {
        ws.send(JSON.stringify({
          type: "resize",
          cols: term.cols,
          rows: term.rows,
        }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type: string; data?: string; message?: string };
        if (msg.type === "output" && msg.data) {
          term.write(msg.data);
        } else if (msg.type === "error" && msg.message) {
          term.writeln(`\x1b[31m[error]\x1b[0m ${msg.message}`);
        } else if (msg.type === "exit") {
          term.writeln("\x1b[33m[disconnected]\x1b[0m PTY session ended.");
        }
      } catch {
        // Malformed message — ignore.
      }
    };

    ws.onerror = () => {
      setError("WebSocket error — backend may be offline.");
      term.writeln("\x1b[31m[error]\x1b[0m WebSocket connection failed.");
    };

    ws.onclose = () => {
      setConnected(false);
      term.writeln("\x1b[33m[disconnected]\x1b[0m WebSocket closed.");
      // Auto-reconnect with jittered backoff (2s, 4s, 8s, …) so the panel
      // recovers from a backend restart without needing a page reload.
      if (reconnectAttemptRef.current < 6) {
        const delay = 1000 * Math.pow(2, reconnectAttemptRef.current);
        reconnectAttemptRef.current += 1;
        term.writeln(
          `\x1b[36m[retry ${reconnectAttemptRef.current}]\x1b[0m reconnecting in ${delay / 1000}s…`
        );
        reconnectTimerRef.current = window.setTimeout(() => {
          connectWebSocket(term);
        }, delay);
      }
    };
  }, []);

  // Stash the latest callback in a ref so the mount effect can invoke it.
  useEffect(() => {
    connectWebSocketRef.current = connectWebSocket;
  }, [connectWebSocket]);

  // Handle panel resize (drag to resize).
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = height;

    const onMove = (ev: MouseEvent) => {
      const delta = startY - ev.clientY;
      setHeight(Math.max(120, Math.min(600, startHeight + delta)));
      if (fitRef.current) {
        fitRef.current.fit();
      }
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  if (!isVisible) {
    return null;
  }

  return (
    <div
      style={
        embedded
          ? {
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              background: "#0F0F0F",
            }
          : {
              position: "fixed",
              bottom: 0,
              left: 0,
              right: 0,
              height: `${height}px`,
              background: "#0F0F0F",
              borderTop: "1px solid #2E2F34",
              display: "flex",
              flexDirection: "column",
              zIndex: 40,
              boxShadow: "0 -8px 24px rgba(0,0,0,0.4)",
            }
      }
    >
      {/* Resize handle (only in floating mode) */}
      {!embedded && (
        <div
          onMouseDown={handleResizeStart}
          style={{
            height: 3,
            cursor: "ns-resize",
            background: "transparent",
            flexShrink: 0,
          }}
        />
      )}
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "4px 12px",
          borderBottom: "1px solid #2E2F34",
          background: "#1A1B1E",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <icons.Terminal size={14} color="#4A9EFF" />
          <span style={{ fontSize: 12, color: "#4A9EFF", fontWeight: 600 }}>
            Nexa Terminal
          </span>
          <span
            style={{
              fontSize: 10,
              padding: "2px 6px",
              borderRadius: 999,
              background: connected ? "rgba(74, 222, 128, 0.15)" : "rgba(248, 113, 113, 0.15)",
              color: connected ? "#4ADE80" : "#F87171",
            }}
          >
            {connected ? "● connected" : "○ disconnected"}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            onClick={() => {
              termRef.current?.writeln("\x1b[33m[clear]\x1b[0m");
              termRef.current?.clear();
            }}
            style={btnStyle}
            title="Clear terminal"
          >
            Clear
          </button>
          <button
            onClick={() => onToggle?.(false)}
            style={btnStyle}
            title="Collapse"
          >
            <icons.ChevronDown size={14} />
          </button>
          {onClose && (
            <button onClick={onClose} style={{ ...btnStyle, color: "#F87171" }} title="Close">
              <icons.X size={14} />
            </button>
          )}
        </div>
      </div>
      {/* Terminal viewport */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: "hidden",
          padding: "4px 8px",
        }}
      />
      {/* Footer hint */}
      <div
        style={{
          padding: "2px 12px",
          borderTop: "1px solid #2E2F34",
          background: "#1A1B1E",
          fontSize: 10,
          color: "#6A6A6A",
          flexShrink: 0,
        }}
      >
        Drag the top edge to resize ·<span style={{ color: "#4A9EFF" }}>nexa-v3.2</span>
        {error && <span style={{ color: "#F87171" }}> · {error}</span>}
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid #2E2F34",
  color: "#9A9A9A",
  padding: "4px 8px",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 11,
  display: "flex",
  alignItems: "center",
  gap: 4,
};
