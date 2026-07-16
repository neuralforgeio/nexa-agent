/**
 * Nexa Agent — Thinking Indicator Component
 *
 * Shows animated "thinking" dots when the agent is processing.
 * Also displays tool call progress with collapsible details.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useState } from "react";
import { ChevronRight, Wrench, Loader2, Check, X, Brain } from "lucide-react";

interface ThinkingIndicatorProps {
  isThinking: boolean;
  toolCalls: Array<{ name: string; result: string; ok: boolean; duration: number }>;
}

export function ThinkingIndicator({ isThinking, toolCalls }: ThinkingIndicatorProps) {
  if (!isThinking && toolCalls.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: 10, padding: "12px 0" }}>
      {/* Avatar */}
      <div style={{
        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
        background: "rgba(74, 158, 255, 0.12)", border: "1px solid rgba(74, 158, 255, 0.3)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <img src="/nexa-agent.png" alt="Nexa" style={{ width: "100%", height: "100%", borderRadius: 6, objectFit: "cover" }} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Thinking label */}
        {isThinking && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#4A9EFF" }}>Nexa</span>
            <div style={{ display: "flex", gap: 3 }}>
              {[0, 1, 2].map((i) => (
                <span key={i} style={{
                  width: 5, height: 5, borderRadius: "50%", background: "#4A9EFF",
                  animation: `nexa-blink 1.4s ease-in-out ${i * 0.2}s infinite`,
                }} />
              ))}
            </div>
            <span style={{ fontSize: 13, color: "#6A6A6A" }}>
              {toolCalls.length > 0 ? `using ${toolCalls.length} tool${toolCalls.length > 1 ? "s" : ""}…` : "thinking…"}
            </span>
          </div>
        )}

        {/* Tool calls */}
        {toolCalls.map((tc, i) => (
          <ToolCallCard key={i} name={tc.name} result={tc.result} ok={tc.ok} duration={tc.duration} />
        ))}
      </div>
    </div>
  );
}

function ToolCallCard({ name, result, ok, duration }: { name: string; result: string; ok: boolean; duration: number }) {
  const [open, setOpen] = useState(false);
  const truncated = result.length > 500;

  return (
    <div style={{
      marginBottom: 6, borderRadius: 8,
      border: `1px solid ${ok ? "rgba(74, 222, 128, 0.2)" : "rgba(248, 113, 113, 0.2)"}`,
      background: ok ? "rgba(74, 222, 128, 0.05)" : "rgba(248, 113, 113, 0.05)",
      overflow: "hidden",
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "transparent", border: "none", cursor: "pointer",
        }}
      >
        <ChevronRight size={14} color="#9A9A9A" style={{
          transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s",
        }} />
        <Wrench size={14} color={ok ? "#4ADE80" : "#F87171"} />
        <span style={{ fontSize: 13, fontWeight: 500, color: ok ? "#4ADE80" : "#F87171" }}>{name}</span>
        <span style={{ fontSize: 11, color: "#6A6A6A" }}>{ok ? "completed" : "failed"}</span>
        <span style={{ fontSize: 11, color: "#6A6A6A", marginLeft: "auto" }}>{duration}ms</span>
      </button>
      {open && (
        <div style={{ padding: "0 12px 12px 36px" }}>
          <pre style={{
            fontSize: 12, color: "#9A9A9A", whiteSpace: "pre-wrap", wordBreak: "break-all",
            maxHeight: 200, overflowY: "auto", margin: 0,
          }}>
            {truncated ? result.slice(0, 500) + "…" : result}
          </pre>
        </div>
      )}
    </div>
  );
}
