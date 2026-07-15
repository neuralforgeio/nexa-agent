"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Loader2, SquareTerminal } from "lucide-react";

interface ComposerProps {
  onSend: (text: string) => void;
  disabled: boolean;
  thinking: boolean;
}

const SUGGESTIONS = [
  "What time is it in Jakarta?",
  "Calculate (128 * 9) + 14.5",
  "Remember that I prefer concise answers",
  "Generate a UUID and explain what it's for",
];

export function Composer({ onSend, disabled, thinking }: ComposerProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  };

  return (
    <div className="border-t border-border bg-background/80 p-3 backdrop-blur">
      <div className="mx-auto max-w-3xl">
        {/* suggestion chips */}
        <div className="mb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => !disabled && onSend(s)}
              disabled={disabled}
              className="flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <SquareTerminal className="h-3 w-3" />
              {s}
            </button>
          ))}
        </div>

        <div className="relative flex items-end gap-2 rounded-xl border border-border bg-input/50 px-3 py-2 focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/30 transition-colors">
          <span className="select-none pb-1.5 text-sm text-emerald-400">▸</span>
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
            placeholder="message nexa…  (enter to send, shift+enter for newline)"
            rows={1}
            disabled={disabled}
            className="flex-1 resize-none bg-transparent py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50 nexa-scroll"
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-emerald-500/40 bg-emerald-500/15 text-emerald-300 transition-colors hover:bg-emerald-500/25 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="send message"
          >
            {thinking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="mt-1.5 px-1 text-center text-[10px] text-muted-foreground/50">
          nexa can call tools — ask it to calculate, recall memory, or check the time.
        </p>
      </div>
    </div>
  );
}
