"use client";

import { useEffect, useRef } from "react";
import { Loader2, Wrench } from "lucide-react";
import type { AgentStep, NexaMessage } from "@/lib/nexa/types";
import { MessageBlock } from "./message-block";
import { ToolStepView } from "./tool-step";
import { NEXA_TAGLINE } from "@/lib/nexa/constants";

interface TranscriptProps {
  messages: NexaMessage[];
  pendingSteps: AgentStep[];
  thinking: boolean;
  welcome: boolean;
  streaming?: boolean;
}

export function Transcript({
  messages,
  pendingSteps,
  thinking,
  welcome,
  streaming,
}: TranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pendingSteps, thinking]);

  if (welcome) return <EmptyState />;

  const toolCount = pendingSteps.filter((s) => s.kind === "tool_call").length;
  const lastIdx = messages.length - 1;

  return (
    <div className="mx-auto max-w-[768px] px-4 py-6">
      <div className="space-y-6">
        {messages.map((m, i) => (
          <MessageBlock
            key={m.id}
            message={m}
            streaming={streaming && i === lastIdx && m.role === "assistant"}
          />
        ))}
      </div>

      {thinking && (
        <div className="mt-6 space-y-2">
          {pendingSteps.length > 0 && (
            <div className="ml-1 space-y-0.5">
              <div className="mb-2 flex items-center gap-2 text-[12px] text-tertiary">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span className="text-primary">Nexa is working</span>
                {toolCount > 0 && (
                  <span className="flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[11px] text-primary">
                    <Wrench className="h-2.5 w-2.5" />
                    {toolCount} tool{toolCount > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              {pendingSteps.map((step, i) => (
                <ToolStepView key={i} step={step} />
              ))}
            </div>
          )}
          {pendingSteps.length === 0 && (
            <div className="flex items-center gap-2 text-[14px] text-tertiary">
              <span className="text-primary font-medium">Nexa</span>
              <span className="nexa-dots">
                <span>•</span>
                <span>•</span>
                <span>•</span>
              </span>
            </div>
          )}
        </div>
      )}

      <div ref={bottomRef} className="h-px" />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4 py-12">
      <div className="relative mb-5 h-20 w-20 overflow-hidden rounded-2xl">
        <img
          src="/nexa-agent.png"
          alt="Nexa Agent"
          className="h-full w-full object-cover"
        />
      </div>
      <h1 className="text-[22px] font-semibold tracking-tight text-foreground">
        Halo, saya Nexa
      </h1>
      <p className="mt-1.5 text-[14px] text-secondary">{NEXA_TAGLINE}</p>
      <p className="mt-4 max-w-md text-center text-[13px] text-tertiary">
        Saya bisa mencari web, membaca/menulis file, menjalankan perintah terminal,
        mengingat preferensi Anda, dan lebih banyak lagi. Mulai dengan mengetik di bawah.
      </p>
    </div>
  );
}
