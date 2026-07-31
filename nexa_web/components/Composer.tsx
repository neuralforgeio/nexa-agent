/**
 * Nexa Agent — Composer Component
 *
 * Pill-shaped input with auto-grow textarea, send button,
 * and suggestion chips for empty state.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface ComposerProps {
  onSend: (text: string) => void;
  disabled: boolean;
  thinking: boolean;
  showSuggestions: boolean;
}

const SUGGESTIONS: Array<{ label: string; prompt: string }> = [
  { label: "💻 Write Code",       prompt: "Write a Python function that computes the nth Fibonacci number using constant space." },
  { label: "🖥 Run Terminal",     prompt: "Show me the contents of the current workspace using the terminal." },
  { label: "🔍 Search Web",       prompt: "Search the web for the latest AI news and summarize the top 3 stories." },
  { label: "📄 Analyze File",     prompt: "Read README.md in this repository and summarize what this project does." },
];

export function Composer({ onSend, disabled, thinking, showSuggestions }: ComposerProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  };

  return (
    <div style={{ background: "linear-gradient(to top, #141618, transparent)", padding: "0 16px 16px" }}>
      <div style={{ maxWidth: 768, margin: "0 auto" }}>
        {/* Suggestions — Z.ai-style quick action chips */}
        {showSuggestions && (
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 8, marginBottom: 12 }}>
            {SUGGESTIONS.map(({ label, prompt }) => (
              <button
                key={label}
                onClick={() => !disabled && onSend(prompt)}
                disabled={disabled}
                style={{
                  padding: "9px 16px", borderRadius: 12, fontSize: 13, fontWeight: 500,
                  border: "1px solid #2E2F34", background: "#191B1E",
                  color: "#CFCFCF", cursor: disabled ? "not-allowed" : "pointer",
                  opacity: disabled ? 0.4 : 1, transition: "all 0.15s",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                }}
                onMouseEnter={(e) => { if (!disabled) { e.currentTarget.style.borderColor = "rgba(74, 158, 255, 0.4)"; e.currentTarget.style.color = "#4A9EFF"; e.currentTarget.style.background = "#1A1B1E"; } }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#2E2F34"; e.currentTarget.style.color = "#CFCFCF"; e.currentTarget.style.background = "#191B1E"; }}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{
          display: "flex", alignItems: "flex-end", gap: 8,
          borderRadius: 24, border: "1px solid #2E2F34", background: "#222327",
          padding: "8px 8px 8px 16px", transition: "border-color 0.15s",
        }}>
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder="Ask Nexa anything…"
            rows={1}
            disabled={disabled}
            style={{
              flex: 1, resize: "none", background: "transparent", border: "none",
              color: "#ECECEC", fontSize: 15, lineHeight: 1.6, fontFamily: "inherit",
              outline: "none", maxHeight: 200, opacity: disabled ? 0.5 : 1,
            }}
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            style={{
              width: 32, height: 32, flexShrink: 0, borderRadius: "50%",
              border: "1px solid rgba(74, 158, 255, 0.4)", background: "rgba(74, 158, 255, 0.15)",
              color: "#4A9EFF", cursor: "pointer", display: "flex",
              alignItems: "center", justifyContent: "center",
              opacity: disabled || !value.trim() ? 0.3 : 1, transition: "opacity 0.15s",
            }}
          >
            {thinking ? <Loader2 size={18} className="animate-spin" /> : <ArrowUp size={18} />}
          </button>
        </div>
        <div style={{ textAlign: "center", fontSize: 11, color: "#6A6A6A", marginTop: 8 }}>
          Nexa can make mistakes. Verify important info.
        </div>
      </div>
    </div>
  );
}
