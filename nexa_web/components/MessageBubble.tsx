/**
 * Nexa Agent — Message Bubble Component (v4.1.0 — Z.ai layout)
 * =================================================================
 *
 * Renders user and assistant messages in the z.ai/OpenClaw hybrid style:
 *
 * - **No bubbles**. Both user and assistant messages span the full width
 *   of the message column, separated by a small avatar on the left.
 * - **User messages** show a subtle accent bar and the user's initials
 *   avatar on the right, mirroring ChatGPT's composer alignment.
 * - **Assistant messages** render real Markdown (headings, bold, code,
 *   lists, tables) via ``Markdown``.
 * - Tool calls appear inline in a collapsible card under the answer.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, User, Wrench } from "lucide-react";
import type { Message } from "../lib/theme";
import { Markdown } from "./Markdown";

interface MessageBubbleProps {
  message: Message;
}

interface ToolCall {
  name: string;
  result: string;
  ok: boolean;
  duration: number;
  /** Optional: original arguments sent to the tool (JSON viewer). */
  args?: string;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const toolCalls: ToolCall[] = message.toolCalls ?? [];

  // ── USER ────────────────────────────────────────────────────────────────
  if (message.role === "user") {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          margin: "0 0 18px",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 12,
            maxWidth: "80%",
            alignItems: "flex-start",
          }}
        >
          <div
            style={{
              minWidth: 0,
              fontSize: 15,
              lineHeight: 1.7,
              color: "#ECECEC",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              // A subtle accent bar, mirroring modern chat UIs.
              borderRight: "3px solid rgba(74, 158, 255, 0.35)",
              paddingRight: 12,
              textAlign: "left",
            }}
          >
            <Markdown>{message.content}</Markdown>
          </div>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              flexShrink: 0,
              background: "#16181c",
              border: "1px solid #24262b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <User size={15} color="#9A9A9A" />
          </div>
        </div>
      </div>
    );
  }

  // ── ASSISTANT ─────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        margin: "0 0 18px",
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: 8,
          flexShrink: 0,
          overflow: "hidden",
          border: "1px solid rgba(74, 158, 255, 0.35)",
          background: "rgba(74, 158, 255, 0.10)",
        }}
      >
        <img
          src="/nexa-agent.png"
          alt="Nexa"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "#4A9EFF",
            marginBottom: 6,
            textTransform: "uppercase",
            letterSpacing: 0.4,
            opacity: 0.9,
          }}
        >
          Nexa
        </div>

        <div style={{ fontSize: 15, lineHeight: 1.7, color: "#ECECEC" }}>
          <Markdown>{message.content}</Markdown>
          {message.thinking && (
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 16,
                marginLeft: 2,
                background: "#4A9EFF",
                animation: "nexa-blink 1s steps(2) infinite",
                verticalAlign: "text-bottom",
              }}
            />
          )}
        </div>

        {/* Tool calls — inline under the answer */}
        {toolCalls.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
            {toolCalls.map((tc, i) => (
              <ToolCallCard key={`${tc.name}-${i}`} call={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCard({ call }: { call: ToolCall }) {
  return <ToolCallCard call={call} />;
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const ok = call.ok;
  const borderColor = ok ? "rgba(74, 222, 128, 0.25)" : "rgba(248, 113, 113, 0.25)";
  const statusColor = ok ? "#4ADE80" : "#F87171";
  const bg = ok ? "rgba(74, 222, 128, 0.05)" : "rgba(248, 113, 113, 0.05)";

  return (
    <div
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
        background: bg,
        overflow: "hidden",
      }}
    >
      <button
        onClick={() => setExpanded((e) => !e)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "#ECECEC",
          fontSize: 12.5,
          fontWeight: 500,
        }}
      >
        {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <Wrench size={13} color={statusColor} />
        <span style={{ fontWeight: 600 }}>{call.name}</span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: statusColor,
            background: ok ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)",
            border: `1px solid ${borderColor}`,
            borderRadius: 4,
            padding: "2px 6px",
            textTransform: "uppercase",
            letterSpacing: 0.5,
          }}
        >
          {ok ? "Success" : "Failed"}
        </span>
        <span style={{ marginLeft: "auto", color: "#6A6A6A" }}>{Math.round(call.duration)}ms</span>
      </button>

      {expanded && (
        <div style={{ padding: "0 12px 10px" }}>
          {call.args && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, color: "#6A6A6A", marginBottom: 2, textTransform: "uppercase" }}>
                Arguments
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: "8px 10px",
                  background: "#0B0C0E",
                  borderRadius: 6,
                  fontSize: 11.5,
                  color: "#CEE1FF",
                  overflowX: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  maxHeight: 160,
                }}
              >
                {call.args}
              </pre>
            </div>
          )}
          <div>
            <div style={{ fontSize: 10, color: "#6A6A6A", marginBottom: 2, textTransform: "uppercase" }}>
              Result
            </div>
            <pre
              style={{
                margin: 0,
                padding: "6px 10px",
                background: "rgba(0,0,0,0.3)",
                borderRadius: 6,
                fontSize: 11.5,
                color: "#9A9A9A",
                maxHeight: 240,
                overflowY: "auto",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {call.result}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
