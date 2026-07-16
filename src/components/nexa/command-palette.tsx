"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Brain,
  Download,
  Eraser,
  Globe,
  Hash,
  HelpCircle,
  Moon,
  Plus,
  Search,
  StickyNote,
  Sun,
  Terminal,
  Wrench,
  Zap,
} from "lucide-react";
import type { SessionItem } from "./sidebar";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onToggleMemory: () => void;
  onToggleNotes: () => void;
  onToggleTheme: () => void;
  onExport: () => void;
  onHelp: () => void;
}

interface PaletteItem {
  id: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  group: "actions" | "sessions";
  action: () => void;
}

export function CommandPalette({
  open,
  onClose,
  onNewSession,
  onSelectSession,
  onToggleMemory,
  onToggleNotes,
  onToggleTheme,
  onExport,
  onHelp,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open && !wasOpen.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
      fetch("/api/sessions", { cache: "no-store" })
        .then((r) => r.json())
        .then((data) => setSessions(data.sessions ?? []))
        .catch(() => {});
    }
    wasOpen.current = open;
  }, [open]);

  const items: PaletteItem[] = useMemo(() => {
    const actions: PaletteItem[] = [
      {
        id: "act-new",
        label: "New session",
        hint: "⌘N",
        icon: Plus,
        group: "actions",
        action: () => {
          onNewSession();
          onClose();
        },
      },
      {
        id: "act-memory",
        label: "Toggle memory panel",
        hint: "⌘E",
        icon: Brain,
        group: "actions",
        action: () => {
          onToggleMemory();
          onClose();
        },
      },
      {
        id: "act-notes",
        label: "Toggle scratchpad",
        hint: "⌘J",
        icon: StickyNote,
        group: "actions",
        action: () => {
          onToggleNotes();
          onClose();
        },
      },
      {
        id: "act-theme",
        label: "Toggle theme",
        hint: "⌘D",
        icon: Sun,
        group: "actions",
        action: () => {
          onToggleTheme();
          onClose();
        },
      },
      {
        id: "act-export",
        label: "Export session as markdown",
        hint: "⌘⇧E",
        icon: Download,
        group: "actions",
        action: () => {
          onExport();
          onClose();
        },
      },
      {
        id: "act-help",
        label: "Show help & tools",
        hint: "?",
        icon: HelpCircle,
        group: "actions",
        action: () => {
          onHelp();
          onClose();
        },
      },
    ];

    const sessionItems: PaletteItem[] = sessions.slice(0, 8).map((s) => ({
      id: `ses-${s.id}`,
      label: s.title,
      hint: `${s.messageCount} msg`,
      icon: Hash,
      group: "sessions" as const,
      action: () => {
        onSelectSession(s.id);
        onClose();
      },
    }));

    return [...actions, ...sessionItems];
  }, [
    sessions,
    onNewSession,
    onSelectSession,
    onToggleMemory,
    onToggleNotes,
    onToggleTheme,
    onExport,
    onHelp,
    onClose,
  ]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.label.toLowerCase().includes(q) ||
        i.hint.toLowerCase().includes(q)
    );
  }, [items, query]);

  // Clamp index to valid range (replaces the setIndex-in-effect pattern).
  const safeIndex = Math.min(index, Math.max(filtered.length - 1, 0));

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setIndex((i) => (i + 1) % Math.max(filtered.length, 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setIndex((i) => (i - 1 + filtered.length) % Math.max(filtered.length, 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        filtered[safeIndex]?.action();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, safeIndex, onClose]);

  if (!open) return null;

  let lastGroup = "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-xl border border-border bg-popover shadow-2xl nexa-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* search input */}
        <div className="flex items-center gap-2.5 border-b border-border px-3.5 py-3">
          <Search className="h-4 w-4 text-primary" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="search commands & sessions…"
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
          />
          <kbd className="rounded border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
            esc
          </kbd>
        </div>

        {/* results */}
        <div className="max-h-[50vh] overflow-y-auto nexa-scroll p-1.5">
          {filtered.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              no matches for "{query}"
            </p>
          )}
          {filtered.map((item, i) => {
            const showGroup = item.group !== lastGroup;
            lastGroup = item.group;
            const Icon = item.icon;
            const active = i === safeIndex;
            return (
              <div key={item.id}>
                {showGroup && (
                  <div className="px-2.5 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                    {item.group === "actions" ? "commands" : "recent sessions"}
                  </div>
                )}
                <button
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => item.action()}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                    active
                      ? "bg-accent text-primary"
                      : "text-foreground/90 hover:bg-muted/60"
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 ${
                      active ? "text-primary" : "text-muted-foreground"
                    }`}
                  />
                  <span className="flex-1 truncate">{item.label}</span>
                  <kbd
                    className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${
                      active
                        ? "border-primary/30 text-primary/80"
                        : "border-border text-muted-foreground/60"
                    }`}
                  >
                    {item.hint}
                  </kbd>
                </button>
              </div>
            );
          })}
        </div>

        {/* footer */}
        <div className="flex items-center justify-between border-t border-border px-3.5 py-2 text-[10px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-muted/60 px-1 py-px">↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border bg-muted/60 px-1 py-px">↵</kbd>
              select
            </span>
          </div>
          <span className="flex items-center gap-1">
            <Zap className="h-2.5 w-2.5 text-primary" />
            nexa command palette
          </span>
        </div>
      </div>
    </div>
  );
}

// silence unused import warning in some builds
void Terminal;
void Wrench;
void Globe;
void Moon;
void Eraser;
