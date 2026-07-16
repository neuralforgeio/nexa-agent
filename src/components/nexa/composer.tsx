"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Globe, Hash, Loader2, Plus, SquareTerminal, Brain } from "lucide-react";

interface ComposerProps {
  onSend: (text: string) => void;
  onCommand?: (cmd: string) => void;
  disabled: boolean;
  thinking: boolean;
  onStop?: () => void;
}

const SUGGESTIONS = [
  { label: "What time is it in Tokyo?", icon: Hash },
  { label: "Calculate (128 × 9) + 14.5", icon: SquareTerminal },
  { label: "Search the web for latest AI news", icon: Globe },
  { label: "Remember that I prefer concise answers", icon: Brain },
];

export function Composer({ onSend, disabled, thinking, onStop }: ComposerProps) {
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
    <div className="bg-gradient-to-t from-background via-background to-transparent px-4 pb-4 pt-2">
      <div className="mx-auto max-w-[768px]">
        {/* Suggestion chips (empty state only) */}
        <div className="mb-3 flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.label}
                onClick={() => !disabled && onSend(s.label)}
                disabled={disabled}
                className="flex items-center gap-1.5 rounded-full border border-border bg-secondary px-3 py-1.5 text-[12px] text-secondary transition-colors hover:border-primary/30 hover:bg-accent hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Icon className="h-3 w-3" />
                {s.label}
              </button>
            );
          })}
        </div>

        {/* Pill composer */}
        <div className="flex items-end gap-2 rounded-[24px] border border-border bg-tertiary px-3 py-2 transition-colors focus-within:border-primary/40">
          <button
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-tertiary transition-colors hover:bg-elevated hover:text-foreground"
            aria-label="more options"
            title="Tools & options"
          >
            <Plus className="h-5 w-5" />
          </button>
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Ask Nexa anything…"
            rows={1}
            disabled={disabled}
            className="flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-relaxed text-foreground placeholder:text-tertiary focus:outline-none disabled:opacity-50 nexa-scroll"
          />
          {thinking && onStop ? (
            <button
              onClick={onStop}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-elevated text-foreground transition-colors hover:bg-tertiary"
              aria-label="stop"
              title="Stop generating"
            >
              <span className="h-3 w-3 rounded-sm bg-foreground" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={disabled || !value.trim()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="send"
            >
              {thinking ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-tertiary">
          Nexa can make mistakes. Verify important info.
        </p>
      </div>
    </div>
  );
}
