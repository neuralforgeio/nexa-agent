/**
 * Nexa Agent — Message Bubble Component
 *
 * Renders user and assistant messages with avatars.
 * User messages are right-aligned bubbles, assistant messages are
 * full-width with the Nexa logo avatar.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { User } from "lucide-react";
import type { Message } from "../lib/theme";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
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
      </div>
    </div>
  );
}
