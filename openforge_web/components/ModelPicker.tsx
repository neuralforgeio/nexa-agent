/**
 * OpenForge — Model Picker (F-05)
 *
 * Compact dropdown pinned to the right of the header. Shows the active
 * provider name + model, and lists every provider from GET /api/provider.
 * Clicking an item POSTs /api/provider/use {name}, applies an optimistic
 * update, and notifies the parent via ``onProviderChange`` so it can
 * re-mount the chat (fresh agent persona/model) if the provider changed.
 *
 * The active provider row gets an accent "ACTIVE" badge.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Cpu, Loader2 } from "lucide-react";

export interface ProviderEntry {
  name: string;
  base_url: string;
  model: string;
  api_key: string;
  is_active: boolean;
}

interface ProviderListResponse {
  active: string | null;
  providers: ProviderEntry[];
}

interface ModelPickerProps {
  /**
   * Called after a successful activation when the active provider actually
   * changed. ``name`` is the newly-active provider name. Parent should
   * re-mount the chat view.
   */
  onProviderChange?: (name: string) => void;
}

export function ModelPicker({ onProviderChange }: ModelPickerProps) {
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [activeName, setActiveName] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/provider", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as ProviderListResponse;
      setProviders(data.providers ?? []);
      setActiveName(data.active ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load providers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Close on outside click / Esc.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const activate = useCallback(
    async (name: string) => {
      if (switching) return;
      const previousActive = activeName;
      setSwitching(name);
      setError(null);
      // Optimistic: flip is_active before the POST completes.
      setProviders((list) =>
        list.map((p) => ({ ...p, is_active: p.name === name }))
      );
      setActiveName(name);
      setOpen(false);
      try {
        const res = await fetch("/api/provider/use", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (previousActive !== name) onProviderChange?.(name);
      } catch (err) {
        // Roll back the optimistic update.
        setProviders((list) =>
          list.map((p) => ({ ...p, is_active: p.name === previousActive }))
        );
        setActiveName(previousActive);
        setError(err instanceof Error ? err.message : "Failed to activate provider");
      } finally {
        setSwitching(null);
      }
    },
    [activeName, onProviderChange, switching]
  );

  const active = providers.find((p) => p.is_active) ?? null;
  const label = loading
    ? "Loading…"
    : active
    ? `${active.name} · ${active.model || "default"}`
    : "Select model";

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        data-testid="model-picker-trigger"
        onClick={() => setOpen((o) => !o)}
        title="Switch LLM provider"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={loading}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          maxWidth: 240,
          padding: "5px 10px",
          borderRadius: 8,
          border: "1px solid var(--forge-border-2, #2E2F34)",
          background: "var(--forge-panel-2, #191B1E)",
          color: "var(--forge-text, #ECECEC)",
          cursor: loading ? "default" : "pointer",
          fontSize: 12,
          fontWeight: 500,
          whiteSpace: "nowrap",
        }}
      >
        {switching ? (
          <Loader2 size={13} className="animate-spin" color="var(--forge-accent, #4A9EFF)" />
        ) : (
          <Cpu size={13} color="var(--forge-accent, #4A9EFF)" />
        )}
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            maxWidth: 170,
          }}
        >
          {label}
        </span>
        <ChevronDown
          size={12}
          color="var(--forge-mute, #6A6A6A)"
          style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}
        />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Providers"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            zIndex: 60,
            minWidth: 260,
            maxWidth: 340,
            maxHeight: 320,
            overflowY: "auto",
            background: "var(--forge-surface, #1A1B1E)",
            border: "1px solid var(--forge-border-2, #2E2F34)",
            borderRadius: 10,
            boxShadow: "0 10px 32px rgba(0,0,0,0.45)",
            padding: 4,
          }}
        >
          {providers.length === 0 && !error && (
            <div style={{ padding: "10px 12px", fontSize: 12, color: "var(--forge-mute, #6A6A6A)" }}>
              No providers configured.
            </div>
          )}
          {error && (
            <div
              role="alert"
              style={{
                padding: "8px 12px",
                fontSize: 12,
                color: "var(--forge-error, #F87171)",
              }}
            >
              {error}
            </div>
          )}
          {providers.map((p) => {
            const isActive = p.is_active;
            return (
              <button
                key={p.name}
                type="button"
                role="option"
                aria-selected={isActive}
                data-testid={`provider-option-${p.name}`}
                onClick={() => activate(p.name)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  border: "none",
                  borderRadius: 7,
                  background: isActive
                    ? "var(--forge-accent-soft, rgba(74,158,255,0.12))"
                    : "transparent",
                  color: "var(--forge-text, #ECECEC)",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => {
                  if (!isActive)
                    e.currentTarget.style.background = "var(--forge-panel-2, #1A1B1E)";
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.background = "transparent";
                }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 13,
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    <span
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {p.name}
                    </span>
                    {isActive && (
                      <span
                        data-testid="provider-active-badge"
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: 0.5,
                          padding: "1px 6px",
                          borderRadius: 999,
                          background: "var(--forge-accent, #4A9EFF)",
                          color: "#fff",
                        }}
                      >
                        ACTIVE
                      </span>
                    )}
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontSize: 11,
                      color: "var(--forge-mute, #6A6A6A)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      marginTop: 1,
                    }}
                  >
                    {p.model || "(default model)"} · {p.base_url || "(env)"}
                  </span>
                </span>
                {isActive && (
                  <Check size={13} color="var(--forge-accent, #4A9EFF)" style={{ flexShrink: 0 }} />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
