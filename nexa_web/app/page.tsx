/**
 * Nexa Agent — Main Chat Page (v4.1.0 — Security + Virtual Multi-Agent)
 *
 * Layout:
 *   [Sidebar | Chat | Sandbox(right, resizable 50/50 preview+terminal)]
 *
 * Features:
 * - Ctrl+B (⌘B) toggles sidebar
 * - Sidebar lists sessions from the local ~/.nexa store, deletable
 * - Thinking steps streamed into a collapsible "Working Process" panel
 *   (auto-collapses 800ms after completion, shows summary)
 * - Sandbox panel on the right: live web preview (auto-detect dev servers)
 *   on top, real PTY terminal below; draggable divider, per-panel close
 * - Duplicate-request guard via in-flight ref
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, X, Zap, PanelRight, PanelLeft } from "lucide-react";
import { Sidebar, CollapsedSidebar } from "../components/Sidebar";
import { MessageBubble } from "../components/MessageBubble";
import { Composer } from "../components/Composer";
import { ThemeToggle } from "../components/ThemeToggle";
import { ModelPicker } from "../components/ModelPicker";
import { ShortcutsHelp, useShortcutsHelp } from "../components/ShortcutsHelp";
import { WorkingProcess, type ThinkingStep } from "../components/WorkingProcess";
import { SandboxPanel } from "../components/SandboxPanel";
import { sendChatMessage, persistTurn } from "../lib/stream";
import type { Message, ChatEvent, SessionMessage } from "../lib/theme";

const LS_SIDEBAR = "nexa-sidebar-open";
const LS_SANDBOX = "nexa-sandbox-open";

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [steps, setSteps] = useState<ThinkingStep[]>([]);
  const [summary, setSummary] = useState<string>("");
  const [refreshKey, setRefreshKey] = useState(0);
  // Three sidebar modes (v4.1.0): ``open`` (264px, full history),
  // ``mini`` (52px, icon-only), ``closed`` (hidden). Ctrl+B cycles
  // open ↔ mini.
  type SidebarMode = "open" | "mini" | "closed";
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("open");
  // Sandbox starts CLOSED. It opens only when the user presses Ctrl+J
  // (or clicks the toggle). This prevents the sandbox from loading
  // the Nexa UI itself on first paint.
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [appVersion, setAppVersion] = useState<string>("4.1.0");
  // Bumping this key re-mounts the chat column (F-05: when the provider /
  // model changes we want a fresh conversation against the new persona).
  const [chatKey, setChatKey] = useState(0);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  // F-07: keyboard shortcuts overlay, toggled by pressing "?".
  const { open: showShortcuts, setOpen: setShowShortcuts } = useShortcutsHelp();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inFlightRef = useRef(false);
  // F-01: AbortController for the in-flight chat stream so the Composer
  // "Stop" button cancels it deterministically.
  const abortRef = useRef<AbortController | null>(null);

  // Hydrate panel state from localStorage. Default to AUTO (open with
  // sidebar, closed with sandbox) when no preference is stored yet.
  useEffect(() => {
    const side = localStorage.getItem(LS_SIDEBAR);
    const sand = localStorage.getItem(LS_SANDBOX);
    // Stored value: "1"|"0"|"mini". Backwards-compat: "0" means closed.
    if (side === "mini") setSidebarMode("mini");
    else setSidebarMode(side === null ? "open" : side === "0" ? "closed" : "open");
    setSandboxOpen(sand === "1");
  }, []);

  // Ctrl+B cycles: open → mini → open (closed is only an explicit state).
  const toggleSidebar = useCallback(() => {
    setSidebarMode((m) => {
      const next: SidebarMode = m === "open" ? "mini" : "open";
      localStorage.setItem(LS_SIDEBAR, next);
      return next;
    });
  }, []);
  const toggleSandbox = useCallback(() => {
    setSandboxOpen((o) => {
      localStorage.setItem(LS_SANDBOX, o ? "0" : "1");
      return !o;
    });
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        toggleSandbox();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleSidebar, toggleSandbox]);

  // Version from backend
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { version?: string };
        if (!cancelled && data.version) setAppVersion(data.version);
      } catch { /* keep default */ }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, steps, thinking]);

  const onSend = useCallback(
    async (text: string) => {
      // Duplicate-request guard: block while a request is in flight.
      if (thinking || inFlightRef.current) return;
      inFlightRef.current = true;

      // F-01: prepare an AbortController so a Stop click cancels this fetch.
      const controller = new AbortController();
      abortRef.current = controller;

      const userMsg: Message = {
        id: `u-${Date.now()}`,
        role: "user",
        content: text,
        createdAt: new Date().toISOString(),
      };
      setMessages((m) => [...m, userMsg]);
      setThinking(true);
      setSteps([]);
      setSummary("");

      const newSteps: ThinkingStep[] = [];
      let accText = "";
      const collectedTools: Array<{ name: string; result: string; ok: boolean; duration: number; args?: string }> = [];
      const asstId = `a-${Date.now()}`;

      setMessages((m) => [
        ...m,
        { id: asstId, role: "assistant", content: "", thinking: true, createdAt: new Date().toISOString() },
      ]);

      const pushStep = (s: Omit<ThinkingStep, "id">) => {
        const step: ThinkingStep = { ...s, id: `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` };
        newSteps.push(step);
        setSteps([...newSteps]);
      };

      try {
        const boundSession = await sendChatMessage(
          text,
          sessionId,
          (event: ChatEvent) => {
          if (event.type === "session" && event.sessionId) {
            setSessionId(event.sessionId);
            setRefreshKey((k) => k + 1);
          } else if (event.type === "thinking" && event.text) {
            pushStep({ kind: "thinking", label: "Thinking", detail: event.text });
          } else if (event.type === "compressing") {
            pushStep({ kind: "thinking", label: "Compressing context", detail: event.detail ?? "Summarizing older messages to fit the context window." });
          } else if (event.type === "memory" && event.memories) {
            pushStep({ kind: "observation", label: "Memory updated", detail: event.memories.map((m) => `• ${m.kind}: ${m.content}`).join("\n") });
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
              args: tr.args,
            });
            pushStep({
              kind: "tool",
              label: tr.tool,
              detail: (tr.args ? `args: ${tr.args.slice(0, 300)}\n\n` : "") + tr.output.slice(0, 400),
              duration_ms: tr.duration_ms,
              ok: tr.ok,
            });
            accText = "";
            setMessages((m) =>
              m.map((msg) => (msg.id === asstId ? { ...msg, content: "", thinking: true } : msg))
            );
          } else if (event.type === "done" && event.answer) {
            setSummary(
              newSteps.length > 0
                ? `Completed with ${newSteps.filter((s) => s.kind === "thinking").length} reasoning steps and ${collectedTools.length} tool call${collectedTools.length === 1 ? "" : "s"}.`
                : "Answered directly."
            );
            setMessages((m) =>
              m.map((msg) =>
                msg.id === asstId
                  ? { ...msg, content: event.answer!, thinking: false, toolCalls: collectedTools.length ? [...collectedTools] : msg.toolCalls }
                  : msg
              )
            );
          } else if (event.type === "error" && event.message) {
            pushStep({ kind: "observation", label: "Error", detail: event.message, ok: false });
            setMessages((m) =>
              m.map((msg) => (msg.id === asstId ? { ...msg, content: `⚠️ ${event.message}`, thinking: false } : msg))
            );
          }
        },
          // onStatus — no UI banner wired yet, so pass undefined.
          undefined,
          // F-01: pass the abort signal so Stop actually aborts the fetch.
          controller.signal
        );

        if (boundSession) {
          const finalContent = accText || messages.find((m) => m.id === asstId)?.content || "";
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
          } catch { /* keep optimistic state */ }
        }
      } finally {
        setThinking(false);
        inFlightRef.current = false;
        // F-01: clear the abort controller once the request settles.
        abortRef.current = null;
      }
    },
    [sessionId, thinking, messages]
  );

  // F-01: stop button — abort the active SSE stream.
  const onStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    // Reflect stop in the UI immediately rather than waiting for the
    // aborted fetch to reject and unwind.
    setThinking(false);
    setMessages((m) =>
      m.map((msg) => (msg.thinking ? { ...msg, thinking: false } : msg))
    );
  }, []);

  const onNew = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setSteps([]);
    setSummary("");
  }, []);

  const onSelect = useCallback((id: string) => {
    if (!id) {
      setSessionId(null);
      setMessages([]);
      return;
    }
    setSessionId(id);
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${id}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { messages?: SessionMessage[] };
        setMessages(
          (data.messages ?? []).map((m) => ({
            id: m.id, role: m.role, content: m.content, toolName: m.toolName, createdAt: m.createdAt,
          }))
        );
        setSteps([]);
        setSummary("");
      } catch { /* ignore */ }
    })();
  }, []);

  const isEmpty = !sessionId && messages.length === 0;
  const lastMsg = messages[messages.length - 1];
  const lastAsstId = lastMsg?.role === "assistant" ? lastMsg.id : null;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--nexa-bg, #0D0E10)", color: "var(--nexa-text, #ECECEC)" }}>
      {/* Sidebar (full / mini icon-only / closed) */}
      {sidebarMode === "open" && (
        <Sidebar activeSessionId={sessionId} onSelect={onSelect} onNew={onNew} refreshKey={refreshKey} />
      )}
      {sidebarMode === "mini" && (
        <CollapsedSidebar onNew={onNew} onExpand={() => setSidebarMode("open")} />
      )}

      {/* Main area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Header */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            borderBottom: "1px solid var(--nexa-border, #24262B)",
            background: "var(--nexa-panel, #111214)",
          }}
        >
          <button
            onClick={toggleSidebar}
            title="Toggle sidebar (Ctrl+B)"
            style={{ background: "none", border: "none", color: "var(--nexa-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
          >
            {sidebarMode === "open" ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span style={{ fontSize: 14, fontWeight: 700, color: "var(--nexa-text, #ECECEC)" }}>Nexa Agent</span>
          <span style={{ fontSize: 11, color: "var(--nexa-mute, #6A6A6A)" }}>v{appVersion}</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 4, alignItems: "center" }}>
            <ModelPicker
              onProviderChange={(name) => {
                // F-05: re-mount the chat on provider change so the new
                // conversation starts against the newly-selected model.
                setActiveProvider(name);
                setSessionId(null);
                setMessages([]);
                setSteps([]);
                setSummary("");
                setChatKey((k) => k + 1);
              }}
            />
            <button
              onClick={toggleSandbox}
              title="Toggle sandbox (Ctrl+J)"
              style={{ background: "none", border: "none", color: sandboxOpen ? "var(--nexa-accent, #4A9EFF)" : "var(--nexa-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
            >
              <PanelRight size={17} />
            </button>
            <button
              onClick={toggleSidebar}
              title="Toggle sidebar (Ctrl+B)"
              style={{ background: "none", border: "none", color: sidebarMode === "open" ? "var(--nexa-accent, #4A9EFF)" : "var(--nexa-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
            >
              <PanelLeft size={17} />
            </button>
            <ThemeToggle />
          </div>
        </header>

        {/* Messages / empty state */}
        <div key={chatKey} style={{ flex: 1, overflowY: "auto" }} data-provider={activeProvider ?? undefined}>
          {isEmpty ? (
            <EmptyState version={appVersion} onPick={(t) => onSend(t)} />
          ) : (
            <div style={{ maxWidth: 820, margin: "0 auto", padding: "24px 16px 120px" }}>
              {messages.map((m) => (
                <div key={m.id}>
                  <MessageBubble message={m} />
                  {m.id === lastAsstId && steps.length > 0 && (
                    <WorkingProcess steps={steps} isActive={thinking} summary={summary} />
                  )}
                </div>
              ))}
              {thinking && !steps.length && (
                <div style={{ padding: "12px 0", color: "#6A6A6A", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ display: "inline-flex", gap: 3 }}>
                    {[0, 1, 2].map((i) => (
                      <span key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#4A9EFF", animation: `nexa-blink 1.2s ease-in-out ${i * 0.15}s infinite` }} />
                    ))}
                  </span>
                  Nexa is thinking…
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <Composer onSend={onSend} onStop={onStop} disabled={thinking} thinking={thinking} showSuggestions={isEmpty} />
      </main>

      {/* Sandbox panel */}
      {sandboxOpen && <SandboxPanel onClose={toggleSandbox} width={480} />}

      {/* F-07: keyboard shortcuts overlay ("?") */}
      {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
    </div>
  );
}

function EmptyState({ version, onPick }: { version: string; onPick: (text: string) => void }) {
  const chips: Array<{ label: string; prompt: string }> = [
    { label: "Build a landing page", prompt: "Create a modern HTML/CSS landing page for a coffee shop and save it as landing.html in the workspace." },
    { label: "Run code", prompt: "Execute a Python snippet that prints the first 20 prime numbers." },
    { label: "Search the web", prompt: "Search the web for today's top AI news and summarize." },
    { label: "Analyze a file", prompt: "Read README.md from the repo and summarize it." },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: 24 }}>
      <div style={{ width: 80, height: 80, borderRadius: 20, marginBottom: 24, overflow: "hidden", border: "1px solid rgba(74, 158, 255, 0.3)" }}>
        <img src="/nexa-agent.png" alt="Nexa Agent" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <h1 style={{ fontSize: 28, fontWeight: 700, color: "#ECECEC", margin: 0, letterSpacing: -0.5 }}>
        What can I build for you?
      </h1>
      <p style={{ fontSize: 15, color: "#9A9A9A", marginTop: 10, textAlign: "center", maxWidth: 440, lineHeight: 1.6 }}>
        Your local AI agent — private by default, with a live sandbox preview and terminal on the right.
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 14, marginBottom: 28 }}>
        <Zap size={14} color="#4A9EFF" />
        <span style={{ fontSize: 13, color: "#6A6A6A" }}>Powered by Nexa Agent v{version}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, maxWidth: 480, width: "100%" }}>
        {chips.map((chip) => (
          <button
            key={chip.label}
            onClick={() => onPick(chip.prompt)}
            style={{ padding: "13px 16px", borderRadius: 12, border: "1px solid #24262B", background: "#141618", color: "#ECECEC", cursor: "pointer", fontSize: 14, textAlign: "left", transition: "border-color 0.15s, background 0.15s" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#4A9EFF"; e.currentTarget.style.background = "#1A1B1E"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#24262B"; e.currentTarget.style.background = "#141618"; }}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </div>
  );
}
