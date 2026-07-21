/**
 * Nexa Agent — Main Chat Page (Hardened v2.1.0)
 *
 * Full chat interface with:
 * - Sidebar (session history, new chat) — desktop + mobile hamburger drawer
 * - Message stream (user bubbles, assistant full-width, tool cards)
 * - Thinking indicator with tool call visualization
 * - SSE streaming from Python agent backend (with reconnect logic in lib/stream.ts)
 * - Empty state with Nexa logo and greeting
 *
 * v2.1.0 fixes:
 * - Mobile sidebar now reachable via hamburger toggle (was hardcoded display:none).
 * - Replaced `any` casts with typed shapes from lib/theme.
 * - Empty state version is no longer hardcoded (read from /api/health).
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Menu, X, Zap, Terminal as TerminalIcon } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import { MessageBubble } from "../components/MessageBubble";
import { ThinkingIndicator } from "../components/ThinkingIndicator";
import { Composer } from "../components/Composer";
import { sendChatMessage, persistTurn } from "../lib/stream";
import type { Message, ChatEvent, SessionMessage } from "../lib/theme";

// v3.0.0: lazy-load TerminalPanel (it uses WebSocket, must be client-only).
const TerminalPanel = dynamic(
  () => import("../components/TerminalPanel").then((m) => m.TerminalPanel),
  { ssr: false }
);

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [toolCalls, setToolCalls] = useState<
    Array<{ name: string; result: string; ok: boolean; duration: number }>
  >([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [appVersion, setAppVersion] = useState<string>("2.1.0");
  const [showTerminal, setShowTerminal] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch the app version from /api/health (no more hardcoded "v1.8.0").
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { version?: string };
        if (!cancelled && data.version) setAppVersion(data.version);
      } catch {
        // keep default
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, thinking, toolCalls]);

  const onSend = useCallback(
    async (text: string) => {
      if (thinking) return;

      const userMsg: Message = {
        id: `u-${Date.now()}`,
        role: "user",
        content: text,
        createdAt: new Date().toISOString(),
      };
      setMessages((m) => [...m, userMsg]);
      setThinking(true);
      setToolCalls([]);

      let accText = "";
      const collectedTools: Array<{
        name: string;
        result: string;
        ok: boolean;
        duration: number;
      }> = [];
      const asstId = `a-${Date.now()}`;

      setMessages((m) => [
        ...m,
        { id: asstId, role: "assistant", content: "", thinking: true, createdAt: new Date().toISOString() },
      ]);

      const boundSession = await sendChatMessage(text, sessionId, (event: ChatEvent) => {
        if (event.type === "session" && event.sessionId) {
          setSessionId(event.sessionId);
          setRefreshKey((k) => k + 1);
        } else if (event.type === "token" && event.text) {
          accText += event.text;
          setMessages((m) =>
            m.map((msg) => (msg.id === asstId ? { ...msg, content: accText, thinking: true } : msg))
          );
        } else if (event.type === "tool_result" && event.toolResult) {
          const tr = event.toolResult;
          collectedTools.push({
            name: tr.tool,
            result: tr.output,
            ok: tr.ok,
            duration: tr.duration_ms,
          });
          setToolCalls([...collectedTools]);
          accText = "";
          setMessages((m) =>
            m.map((msg) => (msg.id === asstId ? { ...msg, content: "", thinking: true } : msg))
          );
        } else if (event.type === "done" && event.answer) {
          // v3.0.0: persist tool calls into the assistant message so they
          // survive a history reload (no more setToolCalls([]) wipe-out).
          setMessages((m) =>
            m.map((msg) =>
              msg.id === asstId
                ? {
                    ...msg,
                    content: event.answer!,
                    thinking: false,
                    toolCalls: collectedTools.length > 0 ? [...collectedTools] : msg.toolCalls,
                  }
                : msg
            )
          );
        } else if (event.type === "error" && event.message) {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === asstId ? { ...msg, content: `⚠️ ${event.message}`, thinking: false } : msg
            )
          );
        }
      });

      setThinking(false);
      // v3.0.0: don't wipe toolCalls — they're persisted in the message now.
      // Only clear the live toolCalls state (the UI reads message.toolCalls).
      setToolCalls([]);
      if (boundSession) {
        const finalContent =
          accText || messages.find((m) => m.id === asstId)?.content || "";
        await persistTurn(
          boundSession,
          text,
          finalContent,
          collectedTools.map((t) => ({ tool: t.name, output: t.result }))
        );
        try {
          const res = await fetch(`/api/sessions/${boundSession}`, { cache: "no-store" });
          if (res.ok) {
            const data = (await res.json()) as { messages?: SessionMessage[] };
            setMessages(
              (data.messages ?? []).map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                toolName: m.toolName,
                createdAt: m.createdAt,
              }))
            );
          }
        } catch {
          /* keep optimistic state */
        }
      }
    },
    [sessionId, thinking, messages]
  );

  const onNew = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setMobileSidebarOpen(false);
  }, []);

  const onSelect = useCallback((id: string) => {
    if (!id) {
      setSessionId(null);
      setMessages([]);
      return;
    }
    setSessionId(id);
    setMobileSidebarOpen(false);
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${id}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { messages?: SessionMessage[] };
        setMessages(
          (data.messages ?? []).map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            toolName: m.toolName,
            createdAt: m.createdAt,
          }))
        );
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const isEmpty = !sessionId && messages.length === 0;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#141618" }}>
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <Sidebar activeSessionId={sessionId} onSelect={onSelect} onNew={onNew} refreshKey={refreshKey} />
      </div>

      {/* Mobile sidebar drawer (hamburger toggle) */}
      {mobileSidebarOpen && (
        <div className="md:hidden" style={{ position: "fixed", inset: 0, zIndex: 50 }}>
          <div
            style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)" }}
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 260 }}>
            <Sidebar
              activeSessionId={sessionId}
              onSelect={onSelect}
              onNew={onNew}
              refreshKey={refreshKey}
            />
          </div>
        </div>
      )}

      {/* Main chat area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Mobile header with hamburger */}
        <div
          className="md:hidden"
          style={{
            display: "flex",
            alignItems: "center",
            padding: "8px 12px",
            borderBottom: "1px solid #2E2F34",
            background: "#1A1B1E",
          }}
        >
          <button
            onClick={() => setMobileSidebarOpen((o) => !o)}
            aria-label="Toggle sidebar"
            style={{
              background: "transparent",
              border: "none",
              color: "#ECECEC",
              cursor: "pointer",
              padding: 6,
              borderRadius: 6,
            }}
          >
            {mobileSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span style={{ marginLeft: 12, color: "#ECECEC", fontWeight: 600 }}>Nexa Agent</span>
        </div>

        {/* Messages or empty state */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {isEmpty ? (
            <EmptyState version={appVersion} onPick={(t) => onSend(t)} />
          ) : (
            <div style={{ maxWidth: 768, margin: "0 auto", padding: "24px 16px" }}>
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <ThinkingIndicator isThinking={thinking} toolCalls={toolCalls} />
              <div ref={scrollRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <Composer onSend={onSend} disabled={thinking} thinking={thinking} showSuggestions={isEmpty} />
      </main>

      {/* v3.0.0: floating terminal toggle button (desktop) */}
      <button
        onClick={() => setShowTerminal((s) => !s)}
        aria-label="Toggle terminal"
        title="Toggle terminal panel"
        style={{
          position: "fixed",
          bottom: 80,
          right: 16,
          width: 40,
          height: 40,
          borderRadius: 8,
          background: showTerminal ? "#4A9EFF" : "#2A2B30",
          border: "1px solid #2E2F34",
          color: "#ECECEC",
          cursor: "pointer",
          zIndex: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <TerminalIcon size={18} />
      </button>

      {/* v3.0.0: terminal panel (collapsible) */}
      {showTerminal && <TerminalPanel onClose={() => setShowTerminal(false)} />}
    </div>
  );
}

function EmptyState({
  version,
  onPick,
}: {
  version: string;
  onPick: (text: string) => void;
}) {
  const chips: Array<{ label: string; prompt: string }> = [
    { label: "Write Code", prompt: "Write a Python function that reverses a string." },
    { label: "Search Web", prompt: "Search the web for the latest AI news." },
    { label: "Analyze File", prompt: "Read and analyze the file notes.txt in the workspace." },
    { label: "Explain Concept", prompt: "Explain how async/await works in Python." },
  ];
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 24,
      }}
    >
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: 20,
          marginBottom: 24,
          overflow: "hidden",
          border: "1px solid rgba(74, 158, 255, 0.3)",
        }}
      >
        <img
          src="/nexa-agent.png"
          alt="Nexa Agent"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 600, color: "#ECECEC", margin: 0 }}>Hello, I&apos;m Nexa</h1>
      <p
        style={{
          fontSize: 15,
          color: "#9A9A9A",
          marginTop: 8,
          textAlign: "center",
          maxWidth: 400,
        }}
      >
        Your advanced AI agent with tool-calling, memory, and real-time web search. Ask me anything to get
        started.
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 16, marginBottom: 24 }}>
        <Zap size={14} color="#4A9EFF" />
        <span style={{ fontSize: 13, color: "#6A6A6A" }}>Powered by Nexa Agent v{version}</span>
      </div>
      {/* Quick action chips */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 10,
          maxWidth: 420,
          width: "100%",
        }}
      >
        {chips.map((chip) => (
          <button
            key={chip.label}
            onClick={() => onPick(chip.prompt)}
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid #2E2F34",
              background: "#1A1B1E",
              color: "#ECECEC",
              cursor: "pointer",
              fontSize: 14,
              textAlign: "left",
              transition: "border-color 0.15s, background 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#4A9EFF";
              e.currentTarget.style.background = "#222327";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#2E2F34";
              e.currentTarget.style.background = "#1A1B1E";
            }}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </div>
  );
}
