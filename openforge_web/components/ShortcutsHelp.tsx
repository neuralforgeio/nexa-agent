/**
 * OpenForge — Keyboard Shortcuts Overlay (F-07)
 *
 * Rendered by the parent when help is open. ``useShortcutsHelp()`` returns
 * ``{open, setOpen}`` and installs a global ``?`` (Shift+/) keydown listener
 * — skipped while typing in inputs. The modal closes on Esc or an outside
 * click, and locks background scroll (overflow:hidden on <body>) while open.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

export interface ShortcutRow {
  keys: string[];
  description: string;
}

export const SHORTCUTS: ShortcutRow[] = [
  { keys: ["Ctrl", "N"], description: "New chat" },
  { keys: ["Ctrl", "K"], description: "Search conversations" },
  { keys: ["Ctrl", ","], description: "Open settings" },
  { keys: ["Ctrl", "B"], description: "Toggle sidebar" },
  { keys: ["Ctrl", "J"], description: "Toggle sandbox panel" },
  { keys: ["/"], description: "Focus composer" },
  { keys: ["Ctrl", "Home"], description: "Scroll to top" },
  { keys: ["Ctrl", "Shift", "Del"], description: "Delete current session" },
  { keys: ["Ctrl", "L"], description: "Stop streaming response" },
  { keys: ["?"], description: "Show this help" },
];

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    el.isContentEditable
  );
}

/**
 * Install the global "?" listener. Returns open state + setter so the page
 * can also open the overlay from a button.
 */
export function useShortcutsHelp(): { open: boolean; setOpen: (o: boolean) => void } {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // "?" is Shift+/ on US layouts — jsdom produces key==="?" directly.
      if (e.key !== "?" && !(e.key === "/" && e.shiftKey)) return;
      if (isTypingTarget(e.target)) return;
      e.preventDefault();
      setOpen((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Lock background scroll while the overlay is open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return { open, setOpen };
}

export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Esc closes (registered on window so it works regardless of focus).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const onOverlayMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === overlayRef.current) onClose();
    },
    [onClose]
  );

  return (
    <div
      ref={overlayRef}
      data-testid="shortcuts-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onMouseDown={onOverlayMouseDown}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 120,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        padding: 20,
      }}
    >
      <div
        style={{
          width: "min(520px, 94vw)",
          maxHeight: "80vh",
          overflowY: "auto",
          background: "var(--forge-surface, #1A1B1E)",
          border: "1px solid var(--forge-border-2, #2E2F34)",
          borderRadius: 14,
          boxShadow: "0 20px 60px rgba(0,0,0,0.55)",
          padding: 22,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 14,
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 16,
              fontWeight: 700,
              color: "var(--forge-text, #ECECEC)",
            }}
          >
            Keyboard shortcuts
          </h2>
          <button
            onClick={onClose}
            aria-label="Close shortcuts help"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--forge-dim, #9A9A9A)",
              cursor: "pointer",
              padding: 4,
              borderRadius: 6,
            }}
          >
            <X size={17} />
          </button>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {SHORTCUTS.map((s, i) => (
              <tr
                key={i}
                style={{
                  borderTop:
                    i === 0 ? "none" : "1px solid var(--forge-border, #24262B)",
                }}
              >
                <td
                  style={{
                    padding: "8px 10px 8px 0",
                    width: "42%",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.keys.map((k, j) => (
                    <span key={j}>
                      {j > 0 && (
                        <span
                          style={{
                            color: "var(--forge-mute, #6A6A6A)",
                            margin: "0 4px",
                            fontSize: 11,
                          }}
                        >
                          +
                        </span>
                      )}
                      <kbd
                        style={{
                          display: "inline-block",
                          padding: "2px 7px",
                          fontSize: 11,
                          fontFamily: "inherit",
                          color: "var(--forge-text, #ECECEC)",
                          background: "var(--forge-panel-2, #191B1E)",
                          border: "1px solid var(--forge-border-2, #2E2F34)",
                          borderBottomWidth: 2,
                          borderRadius: 5,
                        }}
                      >
                        {k}
                      </kbd>
                    </span>
                  ))}
                </td>
                <td
                  style={{
                    padding: "8px 0",
                    fontSize: 13,
                    color: "var(--forge-dim, #9A9A9A)",
                  }}
                >
                  {s.description}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p
          style={{
            margin: "14px 0 0",
            fontSize: 11,
            color: "var(--forge-mute, #6A6A6A)",
            textAlign: "center",
          }}
        >
          Press Esc or click outside to close.
        </p>
      </div>
    </div>
  );
}
