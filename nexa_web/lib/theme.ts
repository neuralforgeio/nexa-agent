/**
 * Nexa Agent — Theme Configuration & Design Tokens
 *
 * Centralized color palette, typography, design tokens, and shared types.
 * Dark mode #141618 (Z.ai-style), accent #4A9EFF.
 *
 * Also hosts formatting helpers (formatTime, formatDate) that previously
 * lived in lib/utils.ts (which depended on clsx + tailwind-merge that
 * weren't in package.json). Those deps are unnecessary; we use plain TS.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

export const colors = {
  bgPrimary: "#141618",
  bgSecondary: "#1A1B1E",
  bgTertiary: "#222327",
  bgElevated: "#2A2B30",
  borderSubtle: "#2E2F34",
  textPrimary: "#ECECEC",
  textSecondary: "#9A9A9A",
  textTertiary: "#6A6A6A",
  accentPrimary: "#4A9EFF",
  accentHover: "#3A8EEF",
  accentSubtle: "rgba(74, 158, 255, 0.12)",
  success: "#4ADE80",
  error: "#F87171",
  warning: "#FBBF24",
} as const;

export const typography = {
  fontSans: "Inter, ui-sans-serif, system-ui, sans-serif",
  fontMono: "JetBrains Mono, ui-monospace, monospace",
  textSize: { xs: "11px", sm: "13px", base: "15px", lg: "18px", xl: "22px" },
  lineHeight: "1.7",
} as const;

export const spacing = {
  maxChatWidth: "768px",
  sidebarWidth: "260px",
  composerRadius: "24px",
  cardRadius: "8px",
} as const;

export type EventType =
  | "session"
  | "thinking"
  | "token"
  | "tool_call"
  | "tool_result"
  | "done"
  | "error"
  | "end"
  | "compressing"
  | "memory"
  // v4.1.6 introspection events
  | "heal"
  | "failover"
  | "expand"
  | "intent"
  | "confidence"
  | "reflection"
  | "suggestions"
  | "autolearn"
  | "patterns"
  | "agent_persona";

export interface ChatEvent {
  type: EventType;
  text?: string;
  sessionId?: string;
  isNew?: boolean;
  toolResult?: {
    tool: string;
    ok: boolean;
    output: string;
    duration_ms: number;
    /** Original JSON arguments the model invoked the tool with (v4.1.0). */
    args?: string;
  };
  detail?: string;
  memories?: Array<{ kind: string; content: string }>;
  answer?: string;
  message?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolName?: string;
  thinking?: boolean;
  toolCalls?: Array<{
    name: string;
    result: string;
    ok: boolean;
    duration: number;
    /** Original JSON arguments the model invoked the tool with. */
    args?: string;
  }>;
  createdAt: string;
}

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

/**
 * Shape of a message as returned by GET /api/sessions/:id.
 * Used when reloading a session's transcript.
 */
export interface SessionMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolName?: string;
  createdAt: string;
}

/**
 * Format an ISO timestamp as HH:MM.
 * Returns "" if the input is invalid.
 */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/**
 * Format an ISO timestamp as a relative day label ("Today", "Yesterday",
 * or "Mon DD"). Returns "" if the input is invalid.
 */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  if (isToday) return "Today";
  if (isYesterday) return "Yesterday";
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}
