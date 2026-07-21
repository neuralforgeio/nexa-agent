/**
 * Nexa Agent — Message Bubble Component (v3.0.0)
 *
 * Renders user and assistant messages with avatars.
 * User messages are right-aligned bubbles, assistant messages are
 * full-width with the Nexa logo avatar.
 *
 * v3.0.0: assistant messages now render persisted tool-call cards below
 * the message text (collapsible).
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useState } from "react";
import { User, ChevronRight, Wrench } from "lucide-react";
import type { Message } from "../lib/theme";

interface MessageBubbleProps {
  message: Message;
}

interface ToolCall {
  name: string;
  result: string;
  ok: boolean;
  duration: number;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const toolCalls: ToolCall[] = message.toolCalls ?? [];

  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 10, maxWidth: "75%" }}>
          <div style={{
            order: 2, width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
            background: "#222327", display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <User size={14} color="#9A9A9A" />
          </div>
          <div style={{
            order: 1, borderRadius: "18px 18px 4px 18px", padding: "10px 16px",
            background: "#222327", fontSize: 15, lineHeight: 1.7, color: "#ECECEC",
            whiteSpace: "pre-wrap", wordBreak: "break-word",
          }}>
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  // Assistant
  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        background: "rgba(74, 158, 255, 0.12)", border: "1px solid rgba(74, 158, 255, 0.3)",
        overflow: "hidden",
      }}>
        <img src="/nexa-agent.png" alt="Nexa" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#4A9EFF", marginBottom: 4 }}>Nexa</div>
        <div style={{ fontSize: 15, lineHeight: 1.7, color: "#ECECEC", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {message.content}
          {message.thinking && (
            <span style={{
              display: "inline-block", width: 8, height: 16, marginLeft: 2,
              background: "#4A9EFF", animation: "nexa-blink 1s steps(2) infinite",
            }} />
          )}
        </div>
        {/* v3.0.0: persisted tool-call cards */}
        {toolCalls.length > 0 && (
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
            {toolCalls.map((tc, idx) => (
              <ToolCallCard key={`${tc.name}-${idx}`} call={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const borderColor = call.ok ? "rgba(74, 222, 128, 0.3)" : "rgba(248, 113, 113, 0.3)";
  const statusColor = call.ok ? "#4ADE80" : "#F87171";

  return (
    <div style={{
      border: `1px solid ${borderColor}`,
      borderRadius: 6,
      background: "rgba(0,0,0,0.2)",
      overflow: "hidden",
    }}>
      <button
        onClick={() => setExpanded((e) => !e)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "6px 10px", background: "transparent", border: "none",
          cursor: "pointer", color: "#ECECEC", fontSize: 12,
        }}
      >
        <ChevronRight
          size={12}
          style={{ transform: expanded ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}
        />
        <Wrench size={12} color={statusColor} />
        <span style={{ fontWeight: 600 }}>{call.name}</span>
        <span style={{ color: statusColor }}>{call.ok ? "✓" : "✗"}</span>
        <span style={{ color: "#6A6A6A", marginLeft: "auto" }}>{Math.round(call.duration)}ms</span>
      </button>
      {expanded && (
        <pre style={{
          margin: 0, padding: "8px 10px", maxHeight: 200, overflowY: "auto",
          fontSize: 12, color: "#9A9A9A", background: "rgba(0,0,0,0.3)",
          whiteSpace: "pre-wrap", wordBreak: "break-word",
        }}>
          {call.result.slice(0, 500)}{call.result.length > 500 ? "…" : ""}
        </pre>
      )}
    </div>
  );
}
