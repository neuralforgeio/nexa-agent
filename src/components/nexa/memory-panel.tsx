"use client";

import { useEffect, useState } from "react";
import { Brain, Plus, Search, Trash2, X } from "lucide-react";
import type { NexaMemory } from "@/lib/nexa/types";

interface MemoryPanelProps {
  onClose?: () => void;
}

export function MemoryPanel({ onClose }: MemoryPanelProps) {
  const [memories, setMemories] = useState<NexaMemory[]>([]);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<NexaMemory["kind"]>("note");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async (q?: string) => {
    setLoading(true);
    try {
      const url = q ? `/api/memory?` : "/api/memory";
      void url;
      const res = await fetch("/api/memory", { cache: "no-store" });
      const data = await res.json();
      const all: NexaMemory[] = data.memories ?? [];
      setMemories(
        q ? all.filter((m) => m.content.toLowerCase().includes(q.toLowerCase())) : all
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const add = async () => {
    const text = content.trim();
    if (!text) return;
    const res = await fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, content: text }),
    });
    if (res.ok) {
      setContent("");
      await load(query);
    }
  };

  const remove = async (id: string) => {
    await fetch(`/api/memory?id=${id}`, { method: "DELETE" });
    await load(query);
  };

  const kindColor: Record<NexaMemory["kind"], string> = {
    note: "text-sky-300 border-sky-500/30 bg-sky-500/10",
    fact: "text-primary border-primary/30 bg-accent",
    preference: "text-amber-300 border-amber-500/30 bg-amber-500/10",
    skill: "text-fuchsia-300 border-fuchsia-500/30 bg-fuchsia-500/10",
  };

  return (
    <aside className="flex h-full w-full flex-col border-l border-border bg-sidebar/40">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <Brain className="h-4 w-4 text-primary" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground">
          Memory
        </h2>
        <span className="text-[10px] text-muted-foreground">
          {memories.length}
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="close memory panel"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* add form */}
      <div className="border-b border-border p-3 space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {(["note", "fact", "preference", "skill"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wider transition-colors ${
                kind === k
                  ? "bg-accent text-primary ring-1 ring-primary/40"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              add();
            }
          }}
          placeholder="remember this…  (⌘+Enter to save)"
          className="w-full resize-none rounded-md border border-border bg-input/60 px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/50 nexa-scroll"
          rows={2}
        />
        <button
          onClick={add}
          disabled={!content.trim()}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-primary/40 bg-accent px-2 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Plus className="h-3.5 w-3.5" />
          save memory
        </button>
      </div>

      {/* search */}
      <div className="border-b border-border p-2">
        <div className="flex items-center gap-2 rounded-md border border-border bg-input/60 px-2 py-1">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              load(e.target.value);
            }}
            placeholder="search memory…"
            className="w-full bg-transparent text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
          />
        </div>
      </div>

      {/* list */}
      <div className="flex-1 overflow-y-auto nexa-scroll p-2 space-y-1.5">
        {loading && memories.length === 0 && (
          <p className="px-2 py-4 text-center text-xs text-muted-foreground">
            loading…
          </p>
        )}
        {!loading && memories.length === 0 && (
          <div className="px-3 py-8 text-center">
            <Brain className="mx-auto mb-2 h-8 w-8 text-muted-foreground/40" />
            <p className="text-xs text-muted-foreground">
              no memories yet.
              <br />
              ask nexa to remember something,
              <br />
              or add one above.
            </p>
          </div>
        )}
        {memories.map((m) => (
          <div
            key={m.id}
            className="group rounded-md border border-border bg-card/40 p-2 nexa-fade-in"
          >
            <div className="mb-1 flex items-center gap-1.5">
              <span
                className={`rounded px-1.5 py-0.5 text-[9px] uppercase tracking-wider ${kindColor[m.kind]}`}
              >
                {m.kind}
              </span>
              <span className="text-[10px] text-muted-foreground/70">
                {new Date(m.createdAt).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <button
                onClick={() => remove(m.id)}
                className="ml-auto rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                aria-label="delete memory"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-foreground/90">{m.content}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}
