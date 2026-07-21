/**
 * Nexa Agent — Terminal Panel (v3.0.0)
 *
 * A lightweight in-browser terminal that connects to the Python backend via
 * WebSocket /ws/terminal. Commands are executed via `run_terminal_command`
 * with all v3.0.0 security boundaries (NEXA_WORKSPACE cwd, ~/.nexa blocked).
 *
 * This is a minimal implementation (no xterm.js dependency) — a styled
 * <pre> for output + a <textarea>-style input. Keeps the bundle small.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, X, ChevronDown, ChevronUp } from "lucide-react";

interface TerminalPanelProps {
  onClose?: () => void;
}

interface OutputLine {
  text: string;
  kind: "stdout" | "stderr" | "error" | "system";
}

export function TerminalPanel({ onClose }: TerminalPanelProps) {
  const [output, setOutput] = useState<OutputLine[]>([
    { text: "Nexa Agent Terminal — commands run in NEXA_WORKSPACE sandbox.", kind: "system" },
    { text: "Type a command and press Enter. Type 'clear' to clear the screen.", kind: "system" },
  ]);
  const [input, setInput] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // Connect to /ws/terminal.
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { type: string; text?: string; message?: string };
        if (msg.type === "output" && msg.text) {
          setOutput((o) => [...o, { text: msg.text!, kind: "stdout" }]);
        } else if (msg.type === "error" && msg.message) {
          setOutput((o) => [...o, { text: msg.message!, kind: "error" }]);
        } else if (msg.type === "done") {
          setOutput((o) => [...o, { text: "", kind: "system" }]);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      setOutput((o) => [...o, { text: "WebSocket error — backend may be offline.", kind: "error" }]);
    };

    return () => {
      ws.close();
    };
  }, []);

  // Auto-scroll to bottom on new output.
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = input.trim();
    if (!cmd) return;
    if (cmd.toLowerCase() === "clear") {
      setOutput([]);
      setInput("");
      return;
    }
    setOutput((o) => [...o, { text: `$ ${cmd}`, kind: "system" }]);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "command", command: cmd }));
    } else {
      setOutput((o) => [...o, { text: "Not connected to backend.", kind: "error" }]);
    }
    setInput("");
  };

  if (collapsed) {
    return (
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          background: "#0F0F0F",
          borderTop: "1px solid #2E2F34",
          padding: "6px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 40,
        }}
      >
        <span style={{ fontSize: 12, color: "#9A9A9A" }}>
          <TerminalIcon size={12} style={{ verticalAlign: "middle", marginRight: 6 }} />
          Terminal
        </span>
        <button
          onClick={() => setCollapsed(false)}
          style={{ background: "transparent", border: "none", color: "#9A9A9A", cursor: "pointer" }}
          aria-label="Expand terminal"
        >
          <ChevronUp size={16} />
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: 220,
        background: "#0F0F0F",
        borderTop: "1px solid #2E2F34",
        display: "flex",
        flexDirection: "column",
        zIndex: 40,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "4px 12px",
          borderBottom: "1px solid #2E2F34",
          background: "#1A1B1E",
        }}
      >
        <span style={{ fontSize: 12, color: "#4A9EFF", fontWeight: 600 }}>
          <TerminalIcon size={12} style={{ verticalAlign: "middle", marginRight: 6 }} />
          Terminal
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setCollapsed(true)}
            style={{ background: "transparent", border: "none", color: "#9A9A9A", cursor: "pointer" }}
            aria-label="Collapse terminal"
          >
            <ChevronDown size={14} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              style={{ background: "transparent", border: "none", color: "#9A9A9A", cursor: "pointer" }}
              aria-label="Close terminal"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Output */}
      <div
        ref={outputRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px 12px",
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        {output.map((line, idx) => (
          <div
            key={idx}
            style={{
              color: line.kind === "error" ? "#F87171" : line.kind === "system" ? "#6A6A6A" : "#ECECEC",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {line.text || "\u00A0"}
          </div>
        ))}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", borderTop: "1px solid #2E2F34", padding: "4px 12px" }}
      >
        <span
          style={{
            color: "#4A9EFF",
            fontFamily: "JetBrains Mono, monospace",
            fontSize: 12,
            marginRight: 8,
            alignSelf: "center",
          }}
        >
          $
        </span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a command..."
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#ECECEC",
            fontFamily: "JetBrains Mono, monospace",
            fontSize: 12,
          }}
          autoComplete="off"
          spellCheck={false}
        />
      </form>
    </div>
  );
}
