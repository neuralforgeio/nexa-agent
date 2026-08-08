/**
 * Nexa Agent — Connection Status Banner (F-08)
 *
 * Polls GET /api/health every ``pollMs`` (default 5000). States:
 *   - loading    → nothing (initial probe hasn't resolved)
 *   - ok         → banner auto-dismissed
 *   - reconnecting → yellow banner (transient failure while probing)
 *   - down       → red banner (backend unreachable / non-OK)
 *
 * The banner auto-dismisses after recovery — no manual close button.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WifiOff, RefreshCw } from "lucide-react";

export type HealthState = "loading" | "ok" | "reconnecting" | "down";

interface Options {
  /** Poll interval in milliseconds. Default 5000. Set falsey to disable. */
  pollMs?: number;
  /** Called after each probe with the resolved state (test hooks). */
  onStateChange?: (state: HealthState) => void;
}

export interface HealthHandle {
  state: HealthState;
  /** Manually re-probe (used by tests + a "retry" affordance). */
  probe: () => Promise<void>;
}

export function useConnectionHealth({ pollMs = 5000, onStateChange }: Options = {}): HealthHandle {
  const [state, setState] = useState<HealthState>("loading");
  const failuresRef = useRef(0);
  const stateRef = useRef<HealthState>("loading");
  const onStateChangeRef = useRef(onStateChange);
  onStateChangeRef.current = onStateChange;

  const probe = useCallback(async () => {
    let ok = false;
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      ok = res.ok;
    } catch {
      ok = false;
    }

    const prev = stateRef.current;
    if (ok) {
      failuresRef.current = 0;
      if (prev !== "ok") {
        stateRef.current = "ok";
        setState("ok");
        onStateChangeRef.current?.("ok");
      }
      return;
    }

    failuresRef.current += 1;
    let next: HealthState;
    if (prev === "loading") next = "down";
    else if (prev === "ok") next = "reconnecting";
    else next = failuresRef.current >= 2 ? "down" : "reconnecting";

    if (next !== prev) {
      stateRef.current = next;
      setState(next);
      onStateChangeRef.current?.(next);
    }
  }, []);

  useEffect(() => {
    void probe();
    if (!pollMs) return;
    const t = setInterval(() => {
      void probe();
    }, pollMs);
    return () => clearInterval(t);
  }, [pollMs, probe]);

  return { state, probe };
}

export function ConnectionStatusBanner({
  state,
  onRetry,
}: {
  state: HealthState;
  onRetry?: () => void;
}) {
  if (state === "ok" || state === "loading") return null;

  const isReconnecting = state === "reconnecting";
  const bg = isReconnecting
    ? "var(--nexa-warning, #FBBF24)"
    : "var(--nexa-error, #F87171)";
  const textColor = "#1B1D21";
  const Icon = isReconnecting ? RefreshCw : WifiOff;

  return (
    <div
      role="alert"
      data-testid="connection-banner"
      data-state={state}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 14px",
        background: bg,
        color: textColor,
        fontSize: 12.5,
        fontWeight: 600,
      }}
    >
      <Icon size={14} style={isReconnecting ? { animation: "nexa-spin 1.4s linear infinite" } : undefined} />
      <span style={{ flex: 1 }}>
        {isReconnecting
          ? "Reconnecting to the Nexa backend…"
          : "Lost connection to the Nexa backend. Retrying automatically."}
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          data-testid="connection-retry"
          style={{
            background: "rgba(0,0,0,0.18)",
            border: "1px solid rgba(0,0,0,0.25)",
            color: textColor,
            borderRadius: 5,
            padding: "2px 8px",
            fontSize: 11,
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Retry now
        </button>
      )}
    </div>
  );
}
