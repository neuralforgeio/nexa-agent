/**
 * Nexa Agent — F-13 Command Palette (Ctrl+K)
 *
 * Overlay dialog with a search input on top and a filterable list of
 * commands below. Each row shows a description on the left, the command
 * name is aligned mid/right, and an optional keyboard shortcut hint sits
 * on the far right.
 *
 * Behavior:
 *   - Ctrl+K (or Cmd+K) toggles the palette open.
 *   - Esc closes it.
 *   - Typing filters commands by name + description.
 *   - ArrowUp / ArrowDown move the highlight.
 *   - Enter executes the highlighted command's action.
 *
 * The list is defined locally; a future release can swap `COMMANDS` for
 * a `/api/commands` fetch without any consumer-side changes.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Command, PlusCircle, Layers, Settings2, Download, Search as SearchIcon,
  SunMoon, Trash2, Keyboard,
} from "lucide-react";

export type CommandId =
  | "new-chat"
  | "new-session"
  | "open-settings"
  | "export-session"
  | "search-sessions"
  | "toggle-theme"
  | "clear-chat"
  | "keyboard-shortcuts";

export interface CommandItem {
  id: CommandId;
  name: string;
  description: string;
  hint?: string;
  icon?: React.ReactNode;
  action?: () => void;
}

const DEFAULT_COMMANDS: CommandItem[] = [
  { id: "new-chat",            name: "New chat",            description: "Start a fresh conversation.",              hint: "Ctrl+N", icon: <PlusCircle size={14} /> },
  { id: "new-session",         name: "New session",         description: "Create a new session bound to the workspace.", hint: "Ctrl+Shift+N", icon: <Layers size={14} /> },
  { id: "open-settings",       name: "Open settings",       description: "Manage providers, models, and skills.",     hint: "Ctrl+,", icon: <Settings2 size={14} /> },
  { id: "export-session",      name: "Export session",      description: "Download the current session as JSON.",     hint: "Ctrl+E", icon: <Download size={14} /> },
  { id: "search-sessions",     name: "Search sessions",     description: "Full-text search across your history.",     hint: "Ctrl+F", icon: <SearchIcon size={14} /> },
  { id: "toggle-theme",        name: "Toggle theme",        description: "Flip between dark and light mode.",         hint: "Ctrl+Shift+L", icon: <SunMoon size={14} /> },
  { id: "clear-chat",          name: "Clear chat",          description: "Remove all messages from the current view.", hint: "Ctrl+Shift+X", icon: <Trash2 size={14} /> },
  { id: "keyboard-shortcuts",  name: "Keyboard shortcuts",  description: "Show all available shortcuts.",             hint: "Ctrl+/", icon: <Keyboard size={14} /> },
];

export interface CommandPaletteProps {
  /** Controlled open state. When omitted, the component manages itself via Ctrl+K. */
  open?: boolean;
  onClose?: () => void;
  /** Override the default command list (useful for tests / custom actions). */
  commands?: CommandItem[];
  /** Fallback handler invoked for commands without their own `action`. */
  onExecute?: (cmd: CommandItem) => void;
}

export function CommandPalette({ open: openProp, onClose, commands, onExecute }: CommandPaletteProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const open = openProp !== undefined ? openProp : internalOpen;
  const list = commands ?? DEFAULT_COMMANDS;

  const close = useCallback(() => {
    setQuery("");
    setActiveIdx(0);
    if (onClose) onClose();
    else setInternalOpen(false);
  }, [onClose]);

  // Global Ctrl+K toggle.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (openProp !== undefined) {
          // Controlled mode: notify parent.
          if (open) close();
        } else {
          setInternalOpen((o) => !o);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, openProp, close]);

  // Focus search input when opened.
  useEffect(() => {
    if (open) {
      // Defer to next tick so the element is mounted.
      const t = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.id.includes(q),
    );
  }, [list, query]);

  // Clamp the highlight as the filtered list shrinks/grows.
  useEffect(() => {
    if (activeIdx >= filtered.length) setActiveIdx(Math.max(0, filtered.length - 1));
  }, [filtered.length, activeIdx]);

  const runCommand = useCallback(
    (cmd: CommandItem) => {
      close();
      if (cmd.action) cmd.action();
      else onExecute?.(cmd);
    },
    [close, onExecute],
  );

  if (!open) return null;

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[activeIdx];
      if (cmd) runCommand(cmd);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "10vh",
      }}
      onMouseDown={close}
    >
      <div
        onMouseDown={(e) => e.stopPropagation()}
        style={{
          width: "min(680px, 92vw)",
          background: "#1A1B1E",
          border: "1px solid #2E2F34",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 12px 40px rgba(0,0,0,0.4)",
        }}
      >
        {/* Search input */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 14px",
            borderBottom: "1px solid #2E2F34",
            background: "#141618",
          }}
        >
          <Command size={16} color="#4A9EFF" />
          <input
            ref={inputRef}
            aria-label="Command search"
            placeholder="Type a command or search…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIdx(0);
            }}
            onKeyDown={onInputKeyDown}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#ECECEC",
              fontSize: 14,
            }}
          />
          <kbd
            style={{
              fontFamily: "inherit",
              fontSize: 11,
              padding: "2px 6px",
              background: "#0F1012",
              border: "1px solid #2E2F34",
              borderRadius: 4,
              color: "#9A9A9A",
            }}
          >
            Esc
          </kbd>
        </div>

        {/* Command list */}
        <div role="listbox" aria-label="Commands" style={{ maxHeight: "50vh", overflowY: "auto" }}>
          {filtered.length === 0 ? (
            <div style={{ padding: "32px 16px", textAlign: "center", color: "#6A6A6A", fontSize: 13 }}>
              No commands match “{query}”.
            </div>
          ) : (
            filtered.map((cmd, idx) => {
              const active = idx === activeIdx;
              return (
                <button
                  key={cmd.id}
                  role="option"
                  aria-selected={active}
                  onClick={() => runCommand(cmd)}
                  onMouseEnter={() => setActiveIdx(idx)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    width: "100%",
                    padding: "10px 14px",
                    background: active ? "rgba(74,158,255,0.10)" : "transparent",
                    border: "none",
                    borderLeft: active ? "2px solid #4A9EFF" : "2px solid transparent",
                    color: "#ECECEC",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: 13,
                  }}
                >
                  <span style={{ color: active ? "#4A9EFF" : "#9A9A9A", flexShrink: 0 }}>
                    {cmd.icon}
                  </span>
                  <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#9A9A9A" }}>
                    {cmd.description}
                  </span>
                  <span style={{ fontWeight: 600, color: "#ECECEC", flexShrink: 0 }}>{cmd.name}</span>
                  {cmd.hint && (
                    <kbd
                      style={{
                        fontFamily: "inherit",
                        fontSize: 10,
                        padding: "2px 6px",
                        background: "#0F1012",
                        border: "1px solid #2E2F34",
                        borderRadius: 4,
                        color: "#9A9A9A",
                        flexShrink: 0,
                      }}
                    >
                      {cmd.hint}
                    </kbd>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
