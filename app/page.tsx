/**
 * Nexa Agent — Main Chat Page
 *
 * Full chat interface with:
 * - Sidebar (session history, new chat)
 * - Message stream (user bubbles, assistant full-width, tool cards)
 * - Thinking indicator with tool call visualization
 * - SSE streaming from Python agent backend
 * - Empty state with Nexa logo and greeting
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Zap } from "lucide-react";
import { Sidebar } from "../nexa_web/components/Sidebar";
import { MessageBubble } from "../nexa_web/components/MessageBubble";
import { ThinkingIndicator } from "../nexa_web/components/ThinkingIndicator";
import { Composer } from "../nexa_web/components/Composer";
import { sendChatMessage, persistTurn } from "../nexa_web/lib/stream";
import type { Message, ChatEvent } from "../nexa_web/lib/theme";

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [toolCalls, setToolCalls] = useState<Array<{ name: string; result: string; ok: boolean; duration: number }>>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, thinking, toolCalls]);

  const onSend = useCallback(async (text: string) => {
    if (thinking) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`, role: "user", content: text, createdAt: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);
    setToolCalls([]);

    // Accumulate streaming response
    let accText = "";
    let collectedTools: Array<{ name: string; result: string; ok: boolean; duration: number }> = [];
    const asstId = `a-${Date.now()}`;

    // Add placeholder assistant message
    setMessages((m) => [...m, { id: asstId, role: "assistant", content: "", thinking: true, createdAt: new Date().toISOString() }]);

    const boundSession = await sendChatMessage(text, sessionId, (event: ChatEvent) => {
      if (event.type === "session" && event.sessionId) {
        setSessionId(event.sessionId);
        setRefreshKey((k) => k + 1);
      } else if (event.type === "thinking") {
        // Already showing thinking indicator
      } else if (event.type === "token" && event.text) {
        accText += event.text;
        setMessages((m) => m.map((msg) => msg.id === asstId ? { ...msg, content: accText, thinking: true } : msg));
      } else if (event.type === "tool_result" && event.toolResult) {
        const tr = event.toolResult;
        collectedTools = [...collectedTools, { name: tr.tool, result: tr.output, ok: tr.ok, duration: tr.duration_ms }];
        setToolCalls([...collectedTools]);
        // Reset accumulator for next LLM round
        accText = "";
        setMessages((m) => m.map((msg) => msg.id === asstId ? { ...msg, content: "", thinking: true } : msg));
      } else if (event.type === "done" && event.answer) {
        setMessages((m) => m.map((msg) => msg.id === asstId ? { ...msg, content: event.answer!, thinking: false } : msg));
      } else if (event.type === "error" && event.message) {
        setMessages((m) => m.map((msg) => msg.id === asstId ? { ...msg, content: `⚠️ ${event.message}`, thinking: false } : msg));
      }
    });

    // Persist
    setThinking(false);
    setToolCalls([]);
    if (boundSession) {
      const finalContent = accText || messages.find(m => m.id === asstId)?.content || "";
      await persistTurn(boundSession, text, finalContent, collectedTools.map(t => ({ tool: t.name, output: t.result })));
      // Reload authoritative transcript
      try {
        const res = await fetch(`/api/sessions/${boundSession}`, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setMessages((data.messages ?? []).map((m: any) => ({
            id: m.id, role: m.role, content: m.content, toolName: m.toolName, createdAt: m.createdAt,
          })));
        }
      } catch { /* keep optimistic state */ }
    }
  }, [sessionId, thinking, messages]);

  const onNew = useCallback(() => {
    setSessionId(null);
    setMessages([]);
  }, []);

  const onSelect = useCallback((id: string) => {
    if (!id) { setSessionId(null); setMessages([]); return; }
    setSessionId(id);
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${id}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        setMessages((data.messages ?? []).map((m: any) => ({
          id: m.id, role: m.role, content: m.content, toolName: m.toolName, createdAt: m.createdAt,
        })));
      } catch { /* ignore */ }
    })();
  }, []);

  const isEmpty = !sessionId && messages.length === 0;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#141618" }}>
      {/* Desktop sidebar */}
      <div style={{ display: "flex" }} className="hidden md:flex">
        <Sidebar activeSessionId={sessionId} onSelect={onSelect} onNew={onNew} refreshKey={refreshKey} />
      </div>

      {/* Mobile sidebar drawer */}
      {sessionId === null && messages.length === 0 && (
        <div className="md:hidden" style={{ display: "none" }}>
          <Sidebar activeSessionId={sessionId} onSelect={onSelect} onNew={onNew} refreshKey={refreshKey} />
        </div>
      )}

      {/* Main chat area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Messages or empty state */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {isEmpty ? (
            <EmptyState />
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
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      height: "100%", padding: 24,
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: 20, marginBottom: 24,
        overflow: "hidden", border: "1px solid rgba(74, 158, 255, 0.3)",
      }}>
        <img src="/nexa-agent.png" alt="Nexa Agent" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 600, color: "#ECECEC", margin: 0 }}>
        Hello, I'm Nexa
      </h1>
      <p style={{ fontSize: 15, color: "#9A9A9A", marginTop: 8, textAlign: "center", maxWidth: 400 }}>
        Your advanced AI agent with tool-calling, memory, and real-time web search.
        Ask me anything to get started.
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 16 }}>
        <Zap size={14} color="#4A9EFF" />
        <span style={{ fontSize: 13, color: "#6A6A6A" }}>Powered by Nexa Agent v1.8.0</span>
      </div>
    </div>
  );
}
