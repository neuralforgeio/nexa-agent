"use client";

import { useState } from "react";
import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp, User } from "lucide-react";
import type { NexaMessage } from "@/lib/nexa/types";
import { Markdown } from "./markdown";

export function MessageBlock({
  message,
  onRegenerate,
}: {
  message: NexaMessage;
  onRegenerate?: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="group flex justify-end nexa-fade-in">
        <div className="flex max-w-[75%] items-start gap-2.5">
          <div className="rounded-2xl rounded-tr-sm bg-tertiary px-4 py-2.5 text-[15px] leading-relaxed text-foreground">
            <div className="whitespace-pre-wrap break-words">{message.content}</div>
          </div>
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-tertiary">
            <User className="h-3.5 w-3.5 text-secondary" />
          </div>
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return (
      <div className="ml-1 nexa-fade-in">
        <div className="rounded-lg border border-border bg-secondary px-3.5 py-2.5">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-tertiary">
            <span className="text-primary">{message.toolName ?? "tool"}</span>
            <span>output</span>
          </div>
          <pre className="nexa-scroll max-h-40 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-foreground/80">
            {message.content}
          </pre>
        </div>
      </div>
    );
  }

  // assistant — full-width, no bubble
  return (
    <div className="group nexa-fade-in">
      <div className="mb-1 flex items-center gap-2">
        <div className="relative h-6 w-6 overflow-hidden rounded-md">
          <img
            src="/nexa-agent.png"
            alt="Nexa"
            className="h-full w-full object-cover"
          />
        </div>
        <span className="text-[13px] font-semibold text-foreground">Nexa</span>
      </div>
      <div className="pl-8">
        <div className="text-[15px] leading-[1.7] text-foreground">
          <Markdown content={message.content} />
        </div>
        {/* per-message actions */}
        <div className="mt-2 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <ActionButton
            icon={Copy}
            onClick={() => navigator.clipboard.writeText(message.content)}
            title="Copy"
          />
          {onRegenerate && (
            <ActionButton icon={RefreshCw} onClick={onRegenerate} title="Regenerate" />
          )}
          <ActionButton icon={ThumbsUp} onClick={() => {}} title="Good response" />
          <ActionButton icon={ThumbsDown} onClick={() => {}} title="Bad response" />
        </div>
      </div>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  onClick,
  title,
}: {
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  title: string;
}) {
  const [active, setActive] = useState(false);
  return (
    <button
      onClick={() => {
        onClick();
        setActive(true);
        setTimeout(() => setActive(false), 1200);
      }}
      className="rounded-md p-1.5 text-tertiary transition-colors hover:bg-tertiary hover:text-foreground"
      title={title}
    >
      {active && title === "Copy" ? (
        <Check className="h-3.5 w-3.5 text-success" />
      ) : (
        <Icon className="h-3.5 w-3.5" />
      )}
    </button>
  );
}
