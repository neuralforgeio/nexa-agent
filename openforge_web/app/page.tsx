/**
 * OpenForge — Main Chat Page (v4.16.0 — rebrand from OpenForge)
 *
 * Layout:
 *   [Sidebar | Chat | Sandbox(right, resizable 50/50 preview+terminal)]
 *
 * Features:
 * - Ctrl+B (⌘B) toggles sidebar
 * - Sidebar lists sessions from the local ~/.openforge store, deletable
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

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Menu, X, Zap, PanelRight, PanelLeft } from "lucide-react";
import { Sidebar, CollapsedSidebar } from "../components/Sidebar";
import { MessageBubble } from "../components/MessageBubble";
import { Composer } from "../components/Composer";
import { ThemeToggle } from "../components/ThemeToggle";
import { ModelPicker } from "../components/ModelPicker";
import { ShortcutsHelp, useShortcutsHelp } from "../components/ShortcutsHelp";
import {
  ConnectionStatusBanner,
  useConnectionHealth,
} from "../components/ConnectionStatusBanner";
import { WorkingProcess, type ThinkingStep } from "../components/WorkingProcess";
import { SandboxPanel } from "../components/SandboxPanel";
import { useIsMobile } from "../lib/useMediaQuery";
import { sendChatMessage, persistTurn } from "../lib/stream";
import { branchSession } from "../lib/sessions";
import type { Message, ChatEvent, SessionMessage } from "../lib/theme";

const LS_SIDEBAR = "forge-sidebar-open";
const LS_SANDBOX = "forge-sandbox-open";

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const [steps, setSteps] = useState<ThinkingStep[]>([]);
  const [summary, setSummary] = useState<string>("");
  const [refreshKey, setRefreshKey] = useState(0);
  // F-01: AbortController for the in-flight chat request.
  const abortRef = useRef<AbortController | null>(null);
  // Three sidebar modes (v4.1.0): ``open`` (264px, full history),
  // ``mini`` (52px, icon-only), ``closed`` (hidden). Ctrl+B cycles
  // open ↔ mini.
  type SidebarMode = "open" | "mini" | "closed";
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("open");
  // Sandbox starts CLOSED. It opens only when the user presses Ctrl+J
  // (or clicks the toggle). This prevents the sandbox from loading
  // the Forge UI itself on first paint.
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [appVersion, setAppVersion] = useState<string>("4.1.0");
  // Bumping this key re-mounts the chat column (F-05: when the provider /
  // model changes we want a fresh conversation against the new persona).
  const [chatKey, setChatKey] = useState(0);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  // F-07: keyboard shortcuts overlay, toggled by pressing "?".
  const { open: showShortcuts, setOpen: setShowShortcuts } = useShortcutsHelp();
  // F-08: top banner that tracks GET /api/health.
  const health = useConnectionHealth();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inFlightRef = useRef(false);
  // (abortRef already declared at line 50 — reused across onSend/onStop/finally.)

  // F-10: true on viewports < 768px (mobile). Sidebar becomes a drawer.
  const isMobile = useIsMobile(768);
  // When the viewport flips to mobile, the sidebar must come up collapsed
  // (drawer) so the content is usable; back to a sane default on desktop.
  useEffect(() => {
    if (isMobile) setSidebarMode("closed");
    // On mobile the sandbox is too wide — close it.
    if (isMobile) setSandboxOpen(false);
  }, [isMobile]);

  // Hydrate panel state from localStorage. Default to AUTO (open with
  // sidebar, closed with sandbox) when no preference is stored yet.
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      return; // F-10: on mobile the effect above defaults to closed.
    }
    const side = localStorage.getItem(LS_SIDEBAR);
    const sand = localStorage.getItem(LS_SANDBOX);
    // Stored value: "1"|"0"|"mini". Backwards-compat: "0" means closed.
    if (side === "mini") setSidebarMode("mini");
    else setSidebarMode(side === null ? "open" : side === "0" ? "closed" : "open");
    setSandboxOpen(sand === "1");
  }, []);

  // Ctrl+B (desktop) cycles open → mini → open.
  // On mobile the sidebar is a drawer: the button toggles open ↔ closed.
  const toggleSidebar = useCallback(() => {
    setSidebarMode((m) => {
      const next: SidebarMode = isMobile
        ? m === "closed" ? "open" : "closed"
        : m === "open" ? "mini" : "open";
      localStorage.setItem(LS_SIDEBAR, next);
      return next;
    });
  }, [isMobile]);
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

  // F-01: user clicked the Stop button — abort the in-flight SSE stream.
  const onStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const onSend = useCallback(
    /**
     * Send a user message through the streaming pipeline.
     *
     * F-02: ``fromIndex`` (optional) — truncate the transcript so that the
     * message at ``fromIndex`` and everything after it is replaced by this
     * new user turn. Used by regenerating (from the triggering user prompt)
     * and edit-&-resubmit (from the edited user bubble).
     */
    async (text: string, fromIndex?: number) => {
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
      // F-02: when fromIndex is set, drop that message and everything after.
      setMessages((m) => {
        const base = typeof fromIndex === "number" ? m.slice(0, fromIndex) : m;
        return [...base, userMsg];
      });
      setThinking(true);
      setSteps([]);
      setSummary("");

      const newSteps: ThinkingStep[] = [];
      let accText = "";
      const collectedTools: Array<{ name: string; result: string; ok: boolean; duration: number; args?: string }> = [];
      const asstId = `a-${Date.now()}`;

      setMessages((m) => {
        const base = typeof fromIndex === "number" ? m.slice(0, fromIndex + 1) : m;
        return [
          ...base,
          { id: asstId, role: "assistant", content: "", thinking: true, createdAt: new Date().toISOString() },
        ];
      });

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
        // F-01: on abort, keep the partial assistant content. Set thinking(false)
        // so the Composer switches back to the send-button state.
        abortRef.current = null;
        setThinking(false);
        inFlightRef.current = false;
      }
    },
    [sessionId, thinking, messages]
  );

  // (OnStop callback moved up before onSend to avoid duplicate-declaration
  // with the F-01 abort handler — only ONE onStop exists in this module.)

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

  // F-02: message actions (regenerate / edit-resubmit / branch).
  const messageActions = useMemo(() => ({
    onRegenerate: (idx: number) => {
      // Find the nearest preceding user prompt for this assistant reply.
      for (let j = idx - 1; j >= 0; j--) {
        if (messages[j]?.role === "user") { void onSend(messages[j].content, j); return; }
      }
    },
    onEditSubmit: (idx: number, text: string) => { void onSend(text, idx); },
    onBranch: async (idx: number) => {
      const m = messages[idx];
      if (!m || !sessionId) return;
      const newId = await branchSession({ sessionId, messageId: m.id });
      if (newId) onSelect(newId);
    },
  }), [messages, sessionId, onSend, onSelect]);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--forge-bg, #0D0E10)", color: "var(--forge-text, #ECECEC)" }}>
      {/* F-10: on mobile the sidebar renders as an overlay drawer. */}
      {isMobile && sidebarMode === "open" && (
        <div
          onClick={() => setSidebarMode("closed")}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            zIndex: 60,
          }}
        />
      )}
      {sidebarMode === "open" && (
        <div
          style={
            isMobile
              ? { position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 61, boxShadow: "8px 0 24px rgba(0,0,0,0.5)" }
              : undefined
          }
        >
          <Sidebar
            activeSessionId={sessionId}
            onSelect={(id) => { onSelect(id); if (isMobile) setSidebarMode("closed"); }}
            onNew={() => { onNew(); if (isMobile) setSidebarMode("closed"); }}
            refreshKey={refreshKey}
          />
        </div>
      )}
      {!isMobile && sidebarMode === "mini" && (
        <CollapsedSidebar onNew={onNew} onExpand={() => setSidebarMode("open")} />
      )}

      {/* Main area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* F-08: connection status banner — red/yellow while unhealthy. */}
        <ConnectionStatusBanner state={health.state} onRetry={health.probe} />
        {/* Header */}
        <header
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            borderBottom: "1px solid var(--forge-border, #24262B)",
            background: "var(--forge-panel, #111214)",
          }}
        >
          <button
            onClick={toggleSidebar}
            title="Toggle sidebar (Ctrl+B)"
            style={{ background: "none", border: "none", color: "var(--forge-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
          >
            {sidebarMode === "open" ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span style={{ fontSize: 14, fontWeight: 700, color: "var(--forge-text, #ECECEC)" }}>OpenForge</span>
          <span style={{ fontSize: 11, color: "var(--forge-mute, #6A6A6A)" }}>v{appVersion}</span>
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
              style={{ background: "none", border: "none", color: sandboxOpen ? "var(--forge-accent, #4A9EFF)" : "var(--forge-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
            >
              <PanelRight size={17} />
            </button>
            <button
              onClick={toggleSidebar}
              title="Toggle sidebar (Ctrl+B)"
              style={{ background: "none", border: "none", color: sidebarMode === "open" ? "var(--forge-accent, #4A9EFF)" : "var(--forge-dim, #9A9A9A)", cursor: "pointer", padding: 4, borderRadius: 6 }}
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
              {messages.map((m, i) => (
                <div key={m.id}>
                  <MessageBubble
                    message={m}
                    index={i}
                    actions={messageActions}
                  />
                  {m.id === lastAsstId && steps.length > 0 && (
                    <WorkingProcess steps={steps} isActive={thinking} summary={summary} />
                  )}
                </div>
              ))}
              {thinking && !steps.length && (
                <div style={{ padding: "12px 0", color: "#6A6A6A", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ display: "inline-flex", gap: 3 }}>
                    {[0, 1, 2].map((i) => (
                      <span key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#4A9EFF", animation: `forge-blink 1.2s ease-in-out ${i * 0.15}s infinite` }} />
                    ))}
                  </span>
                  OpenForge is thinking…
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <Composer onSend={onSend} onStop={onStop} disabled={thinking} thinking={thinking} showSuggestions={isEmpty} />
      </main>

      {/* Sandbox panel — full width on mobile (F-10). */}
      {sandboxOpen && !isMobile && <SandboxPanel onClose={toggleSandbox} width={480} />}

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
        <img src="/icon_shape_open_forge.png" alt="OpenForge" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <h1 style={{ fontSize: 28, fontWeight: 700, color: "#ECECEC", margin: 0, letterSpacing: -0.5 }}>
        What can I build for you?
      </h1>
      <p style={{ fontSize: 15, color: "#9A9A9A", marginTop: 10, textAlign: "center", maxWidth: 440, lineHeight: 1.6 }}>
        Your local AI agent — private by default, with a live sandbox preview and terminal on the right.
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 14, marginBottom: 28 }}>
        <Zap size={14} color="#4A9EFF" />
        <span style={{ fontSize: 13, color: "#6A6A6A" }}>Powered by OpenForge v{version}</span>
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
