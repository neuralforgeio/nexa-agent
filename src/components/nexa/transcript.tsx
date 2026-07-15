"use client";

import { useEffect, useRef } from "react";
import { Cpu, Loader2, Sparkles, Zap } from "lucide-react";
import type { AgentStep, NexaMessage } from "@/lib/nexa/types";
import { MessageBlock } from "./message-block";
import { ToolStepView } from "./tool-step";
import { NEXA_NAME, NEXA_TAGLINE, NEXA_VERSION } from "@/lib/nexa/constants";

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
              </div>
              {pendingSteps.map((step, i) => (
                <ToolStepView key={i} step={step} />
              ))}
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

function Welcome() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="text-center max-w-md">
        <div className="relative mx-auto mb-5 flex h-16 w-16 items-center justify-center">
          <div className="absolute inset-0 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 nexa-glow" />
          <Zap className="relative h-8 w-8 text-emerald-400" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {NEXA_NAME}{" "}
          <span className="text-emerald-400">v{NEXA_VERSION}</span>
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{NEXA_TAGLINE}</p>

        <div className="mt-6 grid gap-2 text-left">
          <Feature
            icon={<Cpu className="h-3.5 w-3.5" />}
            title="Tool-calling core"
            desc="nexa reasons and invokes tools — calculator, clock, memory and more — in an iterative loop."
          />
          <Feature
            icon={<Sparkles className="h-3.5 w-3.5" />}
            title="Persistent memory"
            desc="facts and preferences survive across sessions in the ~/.nexa memory store."
          />
          <Feature
            icon={<Zap className="h-3.5 w-3.5" />}
            title="Terminal-grade UX"
            desc="a CLI-flavoured interface with live tool-call replay and a status bar."
          />
        </div>

        <p className="mt-6 text-xs text-muted-foreground/70">
          send a message below to begin a session.
        </p>
      </div>
    </div>
  );
}

function Feature({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex gap-2.5 rounded-lg border border-border bg-card/40 p-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs font-semibold text-foreground">{title}</div>
        <div className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
          {desc}
        </div>
      </div>
    </div>
  );
}
