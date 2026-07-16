/**
 * Nexa Agent — Theme Configuration
 *
 * Centralized color palette, typography, and design tokens.
 * Dark mode #141618 (Z.ai-style), accent #4A9EFF.
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

export type EventType = "session" | "thinking" | "token" | "tool_call" | "tool_result" | "done" | "error" | "end" | "compressing" | "memory";

export interface ChatEvent {
  type: EventType;
  text?: string;
  sessionId?: string;
  isNew?: boolean;
  toolResult?: { tool: string; ok: boolean; output: string; duration_ms: number };
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
  toolCalls?: Array<{ name: string; result: string; ok: boolean; duration: number }>;
  createdAt: string;
}

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}
