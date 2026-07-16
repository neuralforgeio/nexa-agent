"use client";

import { useCallback, useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
  Brain,
  Command,
  Menu,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  StickyNote,
  Sun,
} from "lucide-react";
import { CommandPalette } from "@/components/nexa/command-palette";
import { Composer } from "@/components/nexa/composer";
import { MemoryPanel } from "@/components/nexa/memory-panel";
import { NotesPanel } from "@/components/nexa/notes-panel";
import { Sidebar } from "@/components/nexa/sidebar";
import { StatusBar } from "@/components/nexa/status-bar";
import { Transcript } from "@/components/nexa/transcript";
import { NEXA_DEFAULT_MODEL, NEXA_VERSION } from "@/lib/nexa/constants";
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
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<NexaMessage[]>([]);
  const [pendingSteps, setPendingSteps] = useState<AgentStep[]>([]);
  const [thinking, setThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  const showHelp = useCallback(() => {
    setMessages((m) => [
      ...m,
      {
        id: `help-${Date.now()}`,
        role: "assistant" as const,
        content: [
          "**Nexa Agent — commands & shortcuts**",
          "",
          "| command | action |",
          "|---|---|",
          "| `/new` · `⌘N` | start a new session |",
          "| `/clear` | clear the current conversation |",
          "| `/memory` · `⌘E` | toggle the memory panel |",
          "| `/notes` · `⌘J` | toggle the scratchpad |",
          "| `/export` · `⌘⇧E` | download this session as markdown |",
          "| `⌘K` | open the command palette |",
          "| `⌘B` | toggle the sidebar |",
          "| `⌘D` | toggle light/dark theme |",
          "| `/help` · `?` | show this help |",
          "",
          "**Available tools (18)**: `web_search`, `web_fetch`, `read_file`, `write_file`, `list_dir`, `run_terminal_command`, `calculate`, `get_time`, `generate_uuid`, `base64`, `save_memory`, `recall_memory`, `list_memory`, `forget_memory`, `save_note`, `list_notes`, `clear_notes`, `echo`.",
          "",
          "Just ask Nexa anything — it will decide which tool (if any) to use.",
        ].join("\n"),
        createdAt: new Date().toISOString(),
      },
    ]);
  }, []);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
        return;
      }
      if (mod && e.key === "n") {
        e.preventDefault();
        setActiveSession(null);
        setMessages([]);
        return;
      }
      if (mod && e.key === "b") {
        e.preventDefault();
        setSidebarOpen((o) => !o);
        return;
      }
      if (mod && e.key === "e") {
        e.preventDefault();
        setMemoryOpen((o) => !o);
        return;
      }
      if (mod && e.key === "j") {
        e.preventDefault();
        setNotesOpen((o) => !o);
        return;
      }
      if (mod && e.key === "d") {
        e.preventDefault();
        toggleTheme();
        return;
      }
      if (mod && e.shiftKey && (e.key === "e" || e.key === "E")) {
        e.preventDefault();
        if (activeSession) window.open(`/api/export/${activeSession}`, "_blank");
        return;
      }
      if (
        e.key === "?" &&
        !mod &&
        !(e.target as HTMLElement)?.closest("input,textarea")
      ) {
        e.preventDefault();
        showHelp();
        return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [theme, activeSession, toggleTheme, showHelp]);

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

  const handleCommand = useCallback(
    (cmd: string) => {
      const c = cmd.trim().toLowerCase();
      if (c === "/new" || c === "/clear") {
        newSession();
        return;
      }
      if (c === "/memory") {
        setMemoryOpen((o) => !o);
        return;
      }
      if (c === "/notes") {
        setNotesOpen((o) => !o);
        return;
      }
      if (c === "/export") {
        if (activeSession) window.open(`/api/export/${activeSession}`, "_blank");
        return;
      }
      if (c === "/help") {
        showHelp();
        return;
      }
    },
    [activeSession, newSession, showHelp]
  );

  const send = useCallback(
    async (text: string) => {
      if (thinking) return;

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
          setMessages((m) => [
            ...m,
            {
              id: `err-${Date.now()}`,
              role: "assistant",
              content: `⚠️ ${data.error ?? "request failed"}\n${data.detail ?? ""}`.trim(),
              createdAt: new Date().toISOString(),
            },
          ]);
          setThinking(false);
          return;
        }

        if (data.isNew || !activeSession) {
          setActiveSession(data.sessionId);
        }
        setRefreshKey((k) => k + 1);

        const toolSteps = data.steps.filter(
          (s) => s.kind === "tool_call" || s.kind === "tool_result"
        );
        if (toolSteps.length > 0) {
          setPendingSteps([]);
          for (let i = 0; i < toolSteps.length; i++) {
            await delay(280);
            setPendingSteps((prev) => [...prev, toolSteps[i]]);
          }
          await delay(200);
        }

        setPendingSteps([]);
        try {
          const sres = await fetch(`/api/sessions/${data.sessionId}`, {
            cache: "no-store",
          });
          if (sres.ok) {
            const sdata = await sres.json();
            setMessages((sdata.messages ?? []) as NexaMessage[]);
          } else {
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
        setMessages((m) => [
          ...m,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `⚠️ network error: ${text}`,
            createdAt: new Date().toISOString(),
          },
        ]);
      } finally {
        setThinking(false);
      }
    },
    [activeSession, thinking]
  );

  const welcome = !activeSession && messages.length === 0;
  const activeTitle =
    messages.find((m) => m.role === "user")?.content?.slice(0, 40) ?? "New chat";

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar — desktop */}
      <div className="hidden w-[260px] shrink-0 border-r border-border lg:block">
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
            className="absolute inset-0 bg-black/60"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-[280px] nexa-slide-up">
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
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center gap-2 border-b border-border bg-background px-3 py-2.5">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-1.5 text-secondary hover:bg-tertiary hover:text-foreground lg:hidden"
            aria-label="open sidebar"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex items-center gap-2">
            <span className="text-[14px] font-medium text-foreground">
              {activeTitle}
            </span>
          </div>

          {/* Model selector pill */}
          <div className="ml-2 hidden items-center gap-1.5 rounded-full border border-border bg-tertiary px-2.5 py-1 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-success nexa-pulse" />
            <span className="text-[12px] text-secondary">{NEXA_DEFAULT_MODEL}</span>
          </div>

          <div className="ml-auto flex items-center gap-1">
            <button
              onClick={() => setPaletteOpen(true)}
              className="flex items-center gap-1.5 rounded-md border border-border bg-tertiary px-2 py-1 text-[12px] text-secondary transition-colors hover:bg-elevated hover:text-foreground"
              aria-label="command palette"
            >
              <Command className="h-3.5 w-3.5" />
              <kbd className="text-[10px] text-tertiary">⌘K</kbd>
            </button>
            {mounted && (
              <button
                onClick={toggleTheme}
                className="rounded-md p-1.5 text-secondary hover:bg-tertiary hover:text-foreground"
                aria-label="toggle theme"
                title="Toggle theme (⌘D)"
              >
                {theme === "dark" ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )}
              </button>
            )}
            <button
              onClick={() => setNotesOpen((o) => !o)}
              className={`rounded-md p-1.5 transition-colors ${
                notesOpen
                  ? "bg-accent text-primary"
                  : "text-secondary hover:bg-tertiary hover:text-foreground"
              }`}
              aria-label="toggle scratchpad"
              title="Scratchpad (⌘J)"
            >
              <StickyNote className="h-4 w-4" />
            </button>
            <button
              onClick={() => setMemoryOpen((o) => !o)}
              className={`rounded-md p-1.5 transition-colors ${
                memoryOpen
                  ? "bg-accent text-primary"
                  : "text-secondary hover:bg-tertiary hover:text-foreground"
              }`}
              aria-label="toggle memory"
              title="Memory (⌘E)"
            >
              {memoryOpen ? (
                <PanelRightClose className="h-4 w-4" />
              ) : (
                <PanelRightOpen className="h-4 w-4" />
              )}
            </button>
          </div>
        </header>

        {/* Chat area */}
        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col">
            <div className="nexa-scroll flex-1 overflow-y-auto">
              <Transcript
                messages={messages}
                pendingSteps={pendingSteps}
                thinking={thinking}
                welcome={welcome}
              />
            </div>
            <Composer onSend={send} disabled={thinking} thinking={thinking} />
          </main>

          {/* Notes panel — desktop */}
          {notesOpen && (
            <div className="hidden w-[280px] shrink-0 border-l border-border lg:block">
              <NotesPanel sessionId={activeSession} />
            </div>
          )}
          {/* Notes panel — mobile */}
          {notesOpen && (
            <div className="fixed inset-0 z-40 lg:hidden">
              <div
                className="absolute inset-0 bg-black/60"
                onClick={() => setNotesOpen(false)}
              />
              <div className="absolute right-0 top-0 h-full w-[300px] nexa-slide-up">
                <NotesPanel
                  sessionId={activeSession}
                  onClose={() => setNotesOpen(false)}
                />
              </div>
            </div>
          )}

          {/* Memory panel — desktop */}
          {memoryOpen && (
            <div className="hidden w-[280px] shrink-0 border-l border-border lg:block">
              <MemoryPanel />
            </div>
          )}
          {/* Memory panel — mobile */}
          {memoryOpen && (
            <div className="fixed inset-0 z-40 lg:hidden">
              <div
                className="absolute inset-0 bg-black/60"
                onClick={() => setMemoryOpen(false)}
              />
              <div className="absolute right-0 top-0 h-full w-[300px] nexa-slide-up">
                <MemoryPanel onClose={() => setMemoryOpen(false)} />
              </div>
            </div>
          )}
        </div>

        {/* Status bar */}
        <StatusBar
          sessionId={activeSession}
          messageCount={messages.length}
          status={thinking ? "thinking" : "idle"}
        />
      </div>

      {/* Command palette */}
      <CommandPalette
        key={paletteOpen ? "open" : "closed"}
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNewSession={newSession}
        onSelectSession={(id) => setActiveSession(id)}
        onToggleMemory={() => setMemoryOpen((o) => !o)}
        onToggleNotes={() => setNotesOpen((o) => !o)}
        onToggleTheme={toggleTheme}
        onExport={() =>
          activeSession && window.open(`/api/export/${activeSession}`, "_blank")
        }
        onHelp={showHelp}
      />
    </div>
  );
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
