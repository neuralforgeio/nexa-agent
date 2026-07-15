"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  Brain,
  Download,
  Eraser,
  Globe,
  Hash,
  HelpCircle,
  Loader2,
  Plus,
  Search,
  SquareTerminal,
} from "lucide-react";

interface ComposerProps {
  onSend: (text: string) => void;
  onCommand?: (cmd: string) => void;
  disabled: boolean;
  thinking: boolean;
}

const SUGGESTIONS = [
  { label: "What time is it in Jakarta?", icon: Hash },
  { label: "Calculate (128 * 9) + 14.5", icon: SquareTerminal },
  { label: "Remember that I prefer concise answers", icon: Brain },
  { label: "Search the web for latest AI news", icon: Globe },
];

interface SlashCommand {
  name: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
}

const SLASH_COMMANDS: SlashCommand[] = [
  { name: "/new", desc: "start a new session", icon: Plus },
  { name: "/clear", desc: "clear current conversation", icon: Eraser },
  { name: "/memory", desc: "toggle memory panel", icon: Brain },
  { name: "/export", desc: "download this session as markdown", icon: Download },
  { name: "/help", desc: "show what nexa can do", icon: HelpCircle },
];

export function Composer({ onSend, onCommand, disabled, thinking }: ComposerProps) {
  const [value, setValue] = useState("");
  const [paletteIndex, setPaletteIndex] = useState(0);
  const [paletteDismissed, setPaletteDismissed] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  const filtered = useMemo(() => {
    const q = value.trim().toLowerCase();
    if (!q.startsWith("/")) return [];
    return SLASH_COMMANDS.filter((c) => c.name.startsWith(q));
  }, [value]);

  const paletteOpen = filtered.length > 0 && !paletteDismissed;

  const runCommand = (name: string) => {
    setValue("");
    setPaletteDismissed(false);
    setPaletteIndex(0);
    onCommand?.(name);
  };

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    if (text.startsWith("/") && filtered.length > 0) {
      runCommand(filtered[paletteIndex].name);
      return;
    }
    if (text.startsWith("/")) {
      runCommand(text);
      return;
    }
    onSend(text);
    setValue("");
    setPaletteDismissed(false);
  };

  return (
    <div className="border-t border-border bg-background/80 p-3 backdrop-blur">
      <div className="mx-auto max-w-3xl">
        {/* suggestion chips */}
        <div className="mb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.label}
                onClick={() => !disabled && onSend(s.label)}
                disabled={disabled}
                className="flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Icon className="h-3 w-3" />
                {s.label}
              </button>
            );
          })}
        </div>

        <div className="relative">
          {/* slash command palette */}
          {paletteOpen && (
            <div className="absolute bottom-full left-0 mb-2 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-xl nexa-fade-in">
              <div className="border-b border-border px-2.5 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                commands
              </div>
              {filtered.map((c, i) => {
                const Icon = c.icon;
                return (
                  <button
                    key={c.name}
                    onMouseEnter={() => setPaletteIndex(i)}
                    onClick={() => runCommand(c.name)}
                    className={`flex w-full items-center gap-2.5 px-2.5 py-2 text-left text-xs transition-colors ${
                      i === paletteIndex
                        ? "bg-emerald-500/15 text-emerald-200"
                        : "text-foreground/90 hover:bg-muted/60"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="font-mono font-semibold">{c.name}</span>
                    <span className="text-muted-foreground">— {c.desc}</span>
                  </button>
                );
              })}
            </div>
          )}

          <div className="flex items-end gap-2 rounded-xl border border-border bg-input/50 px-3 py-2 focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/30 transition-colors">
            <span className="select-none pb-1.5 text-sm text-emerald-400">▸</span>
            <textarea
              ref={ref}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setPaletteDismissed(false);
              }}
              onKeyDown={(e) => {
                if (paletteOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
                  e.preventDefault();
                  setPaletteIndex((i) => {
                    const len = filtered.length;
                    if (e.key === "ArrowDown") return (i + 1) % len;
                    return (i - 1 + len) % len;
                  });
                  return;
                }
                if (paletteOpen && e.key === "Escape") {
                  setPaletteDismissed(true);
                  return;
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder="message nexa…  (enter to send · type / for commands)"
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
        </div>
        <p className="mt-1.5 px-1 text-center text-[10px] text-muted-foreground/50">
          <span className="font-mono text-muted-foreground/70">/</span> for commands ·
          nexa can search the web, calculate, recall memory &amp; more
        </p>
      </div>
    </div>
  );
}
