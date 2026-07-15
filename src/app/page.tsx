"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Brain,
  Menu,
  PanelRightOpen,
  PanelRightClose,
  Zap,
} from "lucide-react";
import { BootSequence } from "@/components/nexa/boot-sequence";
import { Composer } from "@/components/nexa/composer";
import { MemoryPanel } from "@/components/nexa/memory-panel";
import { Sidebar } from "@/components/nexa/sidebar";
import { StatusBar } from "@/components/nexa/status-bar";
import { Transcript } from "@/components/nexa/transcript";
import {
  NEXA_AUTHOR,
  NEXA_NAME,
  NEXA_VERSION,
} from "@/lib/nexa/constants";
import type { AgentStep, NexaMessage } from "@/lib/nexa/types";

interface ChatResponse {
  sessionId: string;
  isNew: boolean;
  answer: string;
  steps: AgentStep[];
  iterations: number;
  error?: string;
  detail?: string;
}

export default function Home() {
  const [booted, setBooted] = useState(false);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<NexaMessage[]>([]);
  const [pendingSteps, setPendingSteps] = useState<AgentStep[]>([]);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Load a session's messages when active changes.
  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/sessions/${activeSession}`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setMessages(data.messages ?? []);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeSession]);

  const newSession = useCallback(() => {
    setActiveSession(null);
    setMessages([]);
    setSidebarOpen(false);
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (thinking) return;

      // Optimistic user message.
      const optimistic: NexaMessage = {
        id: `tmp-${Date.now()}`,
        role: "user",
        content: text,
        createdAt: new Date().toISOString(),
      };
      setMessages((m) => [...m, optimistic]);
      setPendingSteps([]);
      setThinking(true);

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionId: activeSession ?? undefined,
            message: text,
          }),
        });
        const data: ChatResponse = await res.json();

        if (!res.ok) {
          const errMsg: NexaMessage = {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `⚠️ ${data.error ?? "request failed"}\n${data.detail ?? ""}`.trim(),
            createdAt: new Date().toISOString(),
          };
          setMessages((m) => [...m, errMsg]);
          setThinking(false);
          return;
        }

        if (data.isNew || !activeSession) {
          setActiveSession(data.sessionId);
        }
        setRefreshKey((k) => k + 1);

        // Replay tool steps with a stagger for a live-execution feel.
        const toolSteps = data.steps.filter(
          (s) => s.kind === "tool_call" || s.kind === "tool_result"
        );
        if (toolSteps.length > 0) {
          setPendingSteps([]);
          for (let i = 0; i < toolSteps.length; i++) {
            await delay(320);
            setPendingSteps((prev) => [...prev, toolSteps[i]]);
          }
          await delay(280);
        }

        // Commit the authoritative transcript from the server so the local
        // view always matches persisted state (no duplication, no drift).
        setPendingSteps([]);
        try {
          const sres = await fetch(`/api/sessions/${data.sessionId}`, {
            cache: "no-store",
          });
          if (sres.ok) {
            const sdata = await sres.json();
            setMessages((sdata.messages ?? []) as NexaMessage[]);
          } else {
            // Fallback: append the answer only.
            setMessages((m) => [
              ...m,
              {
                id: `asst-${data.sessionId}-${Date.now()}`,
                role: "assistant",
                content: data.answer,
                createdAt: new Date().toISOString(),
              },
            ]);
          }
        } catch {
          setMessages((m) => [
            ...m,
            {
              id: `asst-${data.sessionId}-${Date.now()}`,
              role: "assistant",
              content: data.answer,
              createdAt: new Date().toISOString(),
            },
          ]);
        }
      } catch (err) {
        const text = err instanceof Error ? err.message : String(err);
        const errMsg: NexaMessage = {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `⚠️ network error: ${text}`,
          createdAt: new Date().toISOString(),
        };
        setMessages((m) => [...m, errMsg]);
      } finally {
        setThinking(false);
      }
    },
    [activeSession, thinking]
  );

  const welcome = !activeSession && messages.length === 0;

  return (
    <div className="flex h-screen flex-col bg-background nexa-grid-bg">
      {!booted && <BootSequence onDone={() => setBooted(true)} />}

      {/* Title bar */}
      <header className="flex items-center gap-2 border-b border-border bg-sidebar/60 px-3 py-2 backdrop-blur">
        <button
          onClick={() => setSidebarOpen(true)}
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
          aria-label="open sessions"
        >
          <Menu className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded border border-emerald-500/40 bg-emerald-500/10">
            <Zap className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-bold tracking-tight text-foreground">
              {NEXA_NAME}
            </span>
            <span className="hidden sm:inline text-[10px] text-muted-foreground">
              {NEXA_AUTHOR}
            </span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="hidden sm:inline rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            v{NEXA_VERSION}
          </span>
          <button
            onClick={() => setMemoryOpen((o) => !o)}
            className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${
              memoryOpen
                ? "bg-emerald-500/15 text-emerald-300"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
            aria-label="toggle memory"
          >
            {memoryOpen ? (
              <PanelRightClose className="h-4 w-4" />
            ) : (
              <PanelRightOpen className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">memory</span>
            <Brain className="h-3.5 w-3.5 sm:hidden" />
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex min-h-0 flex-1">
        {/* Sidebar — desktop */}
        <div className="hidden w-64 shrink-0 lg:block">
          <Sidebar
            activeId={activeSession}
            onSelect={(id) => setActiveSession(id || null)}
            onNew={newSession}
            refreshKey={refreshKey}
          />
        </div>

        {/* Sidebar — mobile drawer */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setSidebarOpen(false)}
            />
            <div className="absolute left-0 top-0 h-full w-72 nexa-fade-in">
              <Sidebar
                activeId={activeSession}
                onSelect={(id) => {
                  setActiveSession(id || null);
                  setSidebarOpen(false);
                }}
                onNew={newSession}
                refreshKey={refreshKey}
                onClose={() => setSidebarOpen(false)}
              />
            </div>
          </div>
        )}

        {/* Main column */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="relative flex-1 overflow-y-auto nexa-scroll">
            <Transcript
              messages={messages}
              pendingSteps={pendingSteps}
              thinking={thinking}
              welcome={welcome}
            />
          </div>
          <Composer onSend={send} disabled={thinking} thinking={thinking} />
        </main>

        {/* Memory panel — desktop */}
        {memoryOpen && (
          <div className="hidden w-72 shrink-0 lg:block">
            <MemoryPanel />
          </div>
        )}

        {/* Memory panel — mobile drawer */}
        {memoryOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setMemoryOpen(false)}
            />
            <div className="absolute right-0 top-0 h-full w-80 nexa-fade-in">
              <MemoryPanel onClose={() => setMemoryOpen(false)} />
            </div>
          </div>
        )}
      </div>

      {/* Status bar (sticky footer) */}
      <StatusBar
        sessionId={activeSession}
        messageCount={messages.length}
        status={thinking ? "thinking" : "idle"}
      />
    </div>
  );
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
