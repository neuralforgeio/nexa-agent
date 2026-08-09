/**
 * OpenForge — Working Process Dropdown (v4.1.0 — nested Thought Process)
 * =========================================================================
 *
 * Two-level collapsible panel, inspired by Claude/ChatGPT reasoning UI:
 *
 *   ▼ Working Process (expanded while running; auto-collapses when done)
 *     ▼ Thought Process        ← reasoning chain (sub-dropdown)
 *       - each reasoning step
 *     ▼ Tools                  ← tool calls with timing + result
 *       - write_file …ok 234ms
 *
 * Auto-collapse rule: 400ms after the final answer lands, the WHOLE Working
 * Process collapses. What remains inline is a one-line summary
 *   "Completed with N reasoning steps and M tool calls."
 * Click the summary (or the chevron) to reopen.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Brain,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Wrench,
} from "lucide-react";

export interface ThinkingStep {
  id: string;
  kind: "thinking" | "tool" | "observation" | "sub_thinking";
  label: string;
  detail?: string;
  duration_ms?: number;
  ok?: boolean;
  /** Optional phase marker so we can visually group nested thinking. */
  phase?: string;
}

interface WorkingProcessProps {
  steps: ThinkingStep[];
  isActive: boolean;
  summary?: string;
}

export function WorkingProcess({ steps, isActive, summary }: WorkingProcessProps) {
  const [open, setOpen] = useState(true);
  const [thoughtOpen, setThoughtOpen] = useState(true);
  const [toolsOpen, setToolsOpen] = useState(true);

  // Auto-collapse once the run finishes — keeps the UI out of the way.
  useEffect(() => {
    if (!isActive && steps.length > 0) {
      const t = setTimeout(() => {
        setOpen(false);
        setThoughtOpen(false);
        setToolsOpen(false);
      }, 800);
      return () => clearTimeout(t);
    }
  }, [isActive, steps.length]);

  const thoughts = useMemo(
    () => steps.filter((s) => s.kind === "thinking" || s.kind === "sub_thinking"),
    [steps]
  );
  const toolCalls = useMemo(() => steps.filter((s) => s.kind === "tool"), [steps]);
  const observations = useMemo(
    () => steps.filter((s) => s.kind === "observation"),
    [steps]
  );
  const toolCount = toolCalls.length;

  return (
    <div
      style={{
        margin: "12px 0",
        borderRadius: 12,
        border: "1px solid rgba(74, 158, 255, 0.2)",
        background: "rgba(74, 158, 255, 0.04)",
        overflow: "hidden",
        transition: "all 0.3s ease",
      }}
    >
      {/* ── Outer header ── */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "#ECECEC",
        }}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <Brain size={16} color="#4A9EFF" />
        <span style={{ fontSize: 13, fontWeight: 600 }}>Working Process</span>
        {isActive ? (
          <span style={{ display: "inline-flex", gap: 3, marginLeft: 4 }}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: "50%",
                  background: "#4A9EFF",
                  animation: `nexa-blink 1.2s ease-in-out ${i * 0.15}s infinite`,
                }}
              />
            ))}
          </span>
        ) : (
          <CheckCircle size={14} color="#4ADE80" style={{ marginLeft: 4 }} />
        )}
        <span style={{ fontSize: 12, color: "#6A6A6A", marginLeft: "auto" }}>
          {thoughts.length > 0 && `${thoughts.length} thought${thoughts.length === 1 ? "" : "s"}`}
          {toolCount > 0 && ` · ${toolCount} tool${toolCount === 1 ? "" : "s"}`}
        </span>
      </button>

      {/* ── Outer body ── */}
      {open && (
        <div
          style={{
            padding: "0 14px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {/* Thought Process sub-dropdown */}
          {thoughts.length > 0 && (
            <SubSection
              title="Thought Process"
              count={thoughts.length}
              open={thoughtOpen}
              onToggle={() => setThoughtOpen((o) => !o)}
              accent="#4A9EFF"
            >
              {thoughts.map((step) => (
                <ProcessStep key={step.id} step={step} />
              ))}
            </SubSection>
          )}

          {/* Tools sub-dropdown */}
          {toolCount > 0 && (
            <SubSection
              title={`Tools (${toolCount})`}
              count={toolCount}
              open={toolsOpen}
              onToggle={() => setToolsOpen((o) => !o)}
              accent="#4ADE80"
            >
              {toolCalls.map((step) => (
                <ProcessStep key={step.id} step={step} />
              ))}
            </SubSection>
          )}

          {/* Observations (errors, compress events, memory writes) rendered inline */}
          {observations.map((step) => (
            <ProcessStep key={step.id} step={step} />
          ))}

          {steps.length === 0 && isActive && (
            <div style={{ fontSize: 13, color: "#9A9A9A", padding: "4px 0" }}>
              Initializing reasoning…
            </div>
          )}
        </div>
      )}

      {/* ── Collapsed summary line ── */}
      {!open && !isActive && summary && (
        <div
          style={{
            padding: "0 14px 12px",
            borderTop: "1px solid rgba(74, 158, 255, 0.1)",
            marginTop: 2,
          }}
        >
          <p style={{ fontSize: 13, color: "#9A9A9A", lineHeight: 1.6, margin: 0 }}>
            {summary}
          </p>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────────────────────────────────

function SubSection({
  title,
  count,
  open,
  onToggle,
  accent,
  children,
}: {
  title: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        borderRadius: 8,
        border: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
        overflow: "hidden",
      }}
    >
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "#DEDEDE",
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span style={{ fontSize: 12, fontWeight: 600, color: accent }}>{title}</span>
        <span style={{ fontSize: 11, color: "#6A6A6A", marginLeft: "auto" }}>
          {count}
        </span>
      </button>
      {open && (
        <div
          style={{
            padding: "0 12px 10px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

function ProcessStep({ step }: { step: ThinkingStep }) {
  const isNested = step.kind === "sub_thinking";
  const isObservation = step.kind === "observation";
  const icon =
    step.kind === "tool" ? (
      <Wrench size={13} color={step.ok === false ? "#F87171" : "#4ADE80"} />
    ) : (
      <Brain size={13} color={isObservation ? "#FBBF24" : "#4A9EFF"} />
    );

  return (
    <div
      style={{
        marginLeft: isNested ? 20 : 0,
        padding: "6px 10px",
        borderRadius: 8,
        background: isNested ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.05)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {icon}
        <span
          style={{
            fontSize: 12,
            fontWeight: 500,
            color:
              step.ok === false
                ? "#F87171"
                : isObservation
                ? "#FBBF24"
                : "#DEDEDE",
          }}
        >
          {step.label}
        </span>
        {step.duration_ms !== undefined && (
          <span style={{ fontSize: 11, color: "#6A6A6A", marginLeft: "auto" }}>
            {step.duration_ms}ms
          </span>
        )}
      </div>
      {step.detail && (
        <p
          style={{
            fontSize: 12,
            color: "#9A9A9A",
            margin: "4px 0 0 21px",
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            display: "-webkit-box",
            WebkitLineClamp: 4,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {step.detail}
        </p>
      )}
    </div>
  );
}
