"use client";

import { useEffect, useRef } from "react";
import {
  Brain,
  Clock,
  Cpu,
  Globe,
  Hash,
  Loader2,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import type { AgentStep, NexaMessage } from "@/lib/nexa/types";
import { MessageBlock } from "./message-block";
import { ToolStepView } from "./tool-step";
import {
  NEXA_AUTHOR,
  NEXA_NAME,
  NEXA_TAGLINE,
  NEXA_VERSION,
} from "@/lib/nexa/constants";

interface TranscriptProps {
  messages: NexaMessage[];
  pendingSteps: AgentStep[];
  thinking: boolean;
  welcome: boolean;
}

export function Transcript({
  messages,
  pendingSteps,
  thinking,
  welcome,
}: TranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pendingSteps, thinking]);

  if (welcome) {
    return <Welcome />;
  }

  const toolCount = pendingSteps.filter(
    (s) => s.kind === "tool_call"
  ).length;

  return (
    <div className="mx-auto max-w-3xl px-4 py-5 space-y-4">
      {messages.map((m) => (
        <MessageBlock key={m.id} message={m} />
      ))}

      {thinking && (
        <div className="space-y-2">
          {pendingSteps.length > 0 && (
            <div className="ml-9 space-y-0.5">
              <div className="mb-1.5 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin text-amber-400" />
                <span className="text-amber-400">nexa is working</span>
                {toolCount > 0 && (
                  <span className="ml-1 rounded bg-amber-500/15 px-1.5 py-px text-amber-300/90">
                    {toolCount} tool{toolCount > 1 ? "s" : ""} called
                  </span>
                )}
              </div>
              {pendingSteps.map((step, i) => (
                <ToolStepView key={i} step={step} />
              ))}
              <div className="flex items-center gap-1.5 pt-1.5 text-[10px] text-muted-foreground/60">
                <span className="nexa-cursor">awaiting result</span>
              </div>
            </div>
          )}
          {pendingSteps.length === 0 && (
            <div className="flex gap-2.5 nexa-fade-in">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10">
                <Cpu className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <div className="flex items-center gap-1.5 pt-2 text-xs text-muted-foreground">
                <span className="text-emerald-400">nexa</span>
                <span className="nexa-cursor">thinking</span>
              </div>
            </div>
          )}
        </div>
      )}

      <div ref={bottomRef} className="h-px" />
    </div>
  );
}

const CAPABILITIES = [
  {
    icon: Globe,
    title: "live web search",
    desc: "ask for current news, prices, or facts — nexa searches the web in real time.",
  },
  {
    icon: Cpu,
    title: "tool-calling core",
    desc: "calculator, clock, uuid, base64 — invoked in an iterative reasoning loop.",
  },
  {
    icon: Brain,
    title: "persistent memory",
    desc: "facts & preferences survive across sessions in the ~/.nexa memory store.",
  },
  {
    icon: Terminal,
    title: "terminal-grade UX",
    desc: "live tool-call replay, slash commands, and a status bar.",
  },
];

const EXAMPLES = [
  { icon: Globe, text: "search the web for today's top AI news" },
  { icon: Hash, text: "what time is it in Tokyo right now?" },
  { icon: Cpu, text: "calculate (128 × 9) + 14.5" },
  { icon: Brain, text: "remember that I prefer concise answers" },
];

function Welcome() {
  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* hero */}
        <div className="text-center">
          <div className="relative mx-auto mb-5 flex h-16 w-16 items-center justify-center">
            <div className="absolute inset-0 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 nexa-glow" />
            <div className="absolute inset-0 rounded-2xl border border-emerald-500/20 animate-ping" style={{ animationDuration: "2.5s" }} />
            <Zap className="relative h-8 w-8 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {NEXA_NAME}{" "}
            <span className="text-emerald-400">v{NEXA_VERSION}</span>
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">{NEXA_TAGLINE}</p>
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[10px] text-muted-foreground">
            <Clock className="h-2.5 w-2.5" />
            MIT · © 2026 {NEXA_AUTHOR}
          </div>
        </div>

        {/* capabilities grid */}
        <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {CAPABILITIES.map((c) => {
            const Icon = c.icon;
            return (
              <div
                key={c.title}
                className="flex gap-2.5 rounded-lg border border-border bg-card/40 p-3 transition-colors hover:border-emerald-500/30 hover:bg-emerald-500/5"
              >
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-foreground">
                    {c.title}
                  </div>
                  <div className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                    {c.desc}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* try asking */}
        <div className="mt-5">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            <Sparkles className="h-3 w-3 text-emerald-400" />
            try asking
          </div>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {EXAMPLES.map((e) => {
              const Icon = e.icon;
              return (
                <div
                  key={e.text}
                  className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/20 px-2.5 py-1.5 text-[11px] text-muted-foreground"
                >
                  <Icon className="h-3 w-3 shrink-0 text-emerald-400/70" />
                  <span className="truncate">{e.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        <p className="mt-5 text-center text-[11px] text-muted-foreground/70">
          send a message below, or type{" "}
          <span className="rounded bg-muted px-1 py-px font-mono text-emerald-300">/</span>{" "}
          for commands.
        </p>
      </div>
    </div>
  );
}
