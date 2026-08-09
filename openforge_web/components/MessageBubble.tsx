/**
 * OpenForge — Message Bubble Component (v4.1.0 — Z.ai layout)
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
import {
  ChevronDown, ChevronRight, User, Wrench, Copy, RefreshCw, Pencil, GitBranch, Check, X, Volume2,
} from "lucide-react";
import type { Message } from "../lib/theme";
import { Markdown } from "./Markdown";

/**
 * F-02 message actions.
 *
 * All callbacks are optional: callers may wire only the actions they
 * need. ``index`` is the message position within the current transcript
 * (used by regenerate/edit to find the preceding user prompt).
 */
export interface MessageActions {
  onRegenerate?: (index: number) => void;
  onEditSubmit?: (index: number, newText: string) => void;
  onBranch?: (index: number) => void;
}

interface MessageBubbleProps {
  message: Message;
  /** F-02: index of this message in the messages array (-1 = unknown). */
  index?: number;
  /** F-02: action callbacks (copy is handled internally). */
  actions?: MessageActions;
}

interface ToolCall {
  name: string;
  result: string;
  ok: boolean;
  duration: number;
  /** Optional: original arguments sent to the tool (JSON viewer). */
  args?: string;
}

export function MessageBubble({ message, index = -1, actions }: MessageBubbleProps) {
  const toolCalls: ToolCall[] = message.toolCalls ?? [];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

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
          <div style={{ minWidth: 0 }}>
            {editing ? (
              <div>
                <textarea
                  aria-label="edit-message"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={Math.max(2, draft.split("\n").length)}
                  style={{
                    width: "100%",
                    minWidth: 280,
                    background: "#191B1E",
                    color: "#ECECEC",
                    border: "1px solid rgba(74,158,255,0.4)",
                    borderRadius: 8,
                    padding: "8px 10px",
                    fontSize: 15,
                    lineHeight: 1.6,
                    fontFamily: "inherit",
                    resize: "vertical",
                  }}
                />
                <div style={{ display: "flex", gap: 6, marginTop: 6, justifyContent: "flex-end" }}>
                  <button
                    aria-label="submit-edit"
                    style={{ ...BTN, color: "#4A9EFF", borderColor: "rgba(74,158,255,0.4)" }}
                    onClick={() => {
                      const t = draft.trim();
                      if (!t || t === message.content.trim()) {
                        setDraft(message.content);
                        setEditing(false);
                        return;
                      }
                      if (actions?.onEditSubmit) actions.onEditSubmit(index, t);
                      setEditing(false);
                    }}
                  >
                    <Check size={12} /> Save & resubmit
                  </button>
                  <button aria-label="cancel-edit" style={BTN} onClick={() => { setDraft(message.content); setEditing(false); }}>
                    <X size={12} /> Cancel
                  </button>
                </div>
              </div>
            ) : (
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
            )}
            <ActionBar
              message={message}
              index={index}
              actions={actions}
              editing={editing}
              onStartEdit={() => { setDraft(message.content); setEditing(true); }}
              onStopEdit={() => { setDraft(message.content); setEditing(false); }}
            />
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
        <ActionBar
          message={message}
          index={index}
          actions={actions}
          editing={false}
          onStartEdit={() => {}}
          onStopEdit={() => {}}
        />

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

/* ── F-02: message action toolbar ─────────────────────────────────────── */

const BTN = {
  background: "transparent",
  border: "1px solid #2E2F34",
  color: "#9A9A9A",
  borderRadius: 6,
  padding: "3px 6px",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontSize: 11,
} as const;

function ActionBar({
  message,
  index,
  actions,
  editing,
  onStartEdit,
  onStopEdit,
}: {
  message: Message;
  index: number;
  actions?: MessageActions;
  editing: boolean;
  onStartEdit: () => void;
  onStopEdit: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [branching, setBranching] = useState(false);
  // C-05: speech for this bubble.
  const [speaking, setSpeaking] = useState(false);

  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — ignore */
    }
  };
  const doBranch = async () => {
    if (!actions?.onBranch || branching) return;
    setBranching(true);
    try {
      actions.onBranch(index);
    } finally {
      setBranching(false);
    }
  };

  const toggleSpeak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const u = new SpeechSynthesisUtterance(message.content);
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  };

  return (
    <div
      data-testid="msg-actions"
      style={{ display: "flex", gap: 6, marginTop: 6, opacity: 0.9 }}
    >
      <button aria-label="copy" title="Copy" style={BTN} onClick={doCopy} disabled={editing}>
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "Copied" : "Copy"}
      </button>
      {typeof window !== "undefined" && "speechSynthesis" in window && (
        <button
          aria-label="speak"
          title={speaking ? "Stop speaking" : "Read aloud"}
          style={BTN}
          onClick={toggleSpeak}
        >
          <Volume2 size={12} /> {speaking ? "Stop" : "Listen"}
        </button>
      )}
      {message.role === "assistant" && actions?.onRegenerate && index > 0 && (
        <button
          aria-label="regenerate"
          title="Regenerate"
          style={BTN}
          onClick={() => actions.onRegenerate!(index)}
          disabled={editing}
        >
          <RefreshCw size={12} /> Regenerate
        </button>
      )}
      {message.role === "user" && actions?.onEditSubmit && (
        <button
          aria-label="edit"
          title="Edit & resubmit"
          style={BTN}
          onClick={() => (editing ? onStopEdit() : onStartEdit())}
        >
          {editing ? <X size={12} /> : <Pencil size={12} />} {editing ? "Cancel" : "Edit"}
        </button>
      )}
      {actions?.onBranch && (
        <button
          aria-label="branch"
          title="Branch from here"
          style={BTN}
          onClick={doBranch}
          disabled={branching || editing}
        >
          <GitBranch size={12} /> {branching ? "…" : "Branch"}
        </button>
      )}
    </div>
  );
}

/* ── end F-02 toolbar ─────────────────────────────────────────────────── */

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
