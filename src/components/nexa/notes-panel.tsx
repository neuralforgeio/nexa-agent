"use client";

import { useCallback, useEffect, useState } from "react";
import { Pin, PinOff, Plus, StickyNote, Trash2, X } from "lucide-react";
import type { NexaNoteItem } from "@/lib/nexa/notes";

interface NotesPanelProps {
  sessionId: string | null;
  onClose?: () => void;
}

export function NotesPanel({ sessionId, onClose }: NotesPanelProps) {
  const [notes, setNotes] = useState<NexaNoteItem[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!sessionId) {
      setNotes([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/notes?sessionId=${sessionId}`, {
        cache: "no-store",
      });
      const data = await res.json();
      setNotes(data.notes ?? []);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    const text = content.trim();
    if (!text || !sessionId) return;
    const res = await fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, content: text }),
    });
    if (res.ok) {
      setContent("");
      await load();
    }
  };

  const togglePin = async (id: string) => {
    await fetch(`/api/notes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await load();
  };

  const remove = async (id: string) => {
    await fetch(`/api/notes/${id}`, { method: "DELETE" });
    setNotes((n) => n.filter((x) => x.id !== id));
  };

  const pinnedCount = notes.filter((n) => n.pinned).length;

  return (
    <aside className="flex h-full w-full flex-col border-l border-border bg-sidebar/40">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <StickyNote className="h-4 w-4 text-amber-400" />
        <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground">
          Scratchpad
        </h2>
        <span className="text-[10px] text-muted-foreground">
          {notes.length}
          {pinnedCount > 0 && (
            <span className="ml-1 text-amber-400">· {pinnedCount}★</span>
          )}
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="ml-auto rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="close notes panel"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {!sessionId ? (
        <div className="flex flex-1 items-center justify-center p-4 text-center">
          <div>
            <StickyNote className="mx-auto mb-2 h-8 w-8 text-muted-foreground/40" />
            <p className="text-xs text-muted-foreground">
              start a session to use the scratchpad.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="border-b border-border p-3">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  add();
                }
              }}
              placeholder="jot a working note…  (⌘+Enter to save)"
              className="w-full resize-none rounded-md border border-border bg-input/60 px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-amber-500/50 nexa-scroll"
              rows={2}
            />
            <button
              onClick={add}
              disabled={!content.trim()}
              className="mt-1.5 flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs font-medium text-amber-300 transition-colors hover:bg-amber-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus className="h-3.5 w-3.5" />
              add note
            </button>
          </div>

          <div className="flex-1 overflow-y-auto nexa-scroll p-2 space-y-1.5">
            {loading && notes.length === 0 && (
              <p className="px-2 py-4 text-center text-xs text-muted-foreground">
                loading…
              </p>
            )}
            {!loading && notes.length === 0 && (
              <div className="px-3 py-8 text-center">
                <StickyNote className="mx-auto mb-2 h-8 w-8 text-muted-foreground/40" />
                <p className="text-xs text-muted-foreground">
                  scratchpad is empty.
                  <br />
                  add a note above, or ask
                  <br />
                  nexa to save_note.
                </p>
              </div>
            )}
            {notes.map((n) => (
              <div
                key={n.id}
                className={`group rounded-md border p-2 nexa-fade-in ${
                  n.pinned
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-border bg-card/40"
                }`}
              >
                <div className="mb-1 flex items-center gap-1.5">
                  {n.pinned ? (
                    <Pin className="h-3 w-3 text-amber-400 fill-amber-400" />
                  ) : (
                    <PinOff className="h-3 w-3 text-muted-foreground/40" />
                  )}
                  <span className="text-[10px] text-muted-foreground/70">
                    {new Date(n.createdAt).toLocaleString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <div className="ml-auto flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={() => togglePin(n.id)}
                      className="rounded p-0.5 text-muted-foreground hover:text-amber-400"
                      aria-label="toggle pin"
                    >
                      {n.pinned ? (
                        <PinOff className="h-3 w-3" />
                      ) : (
                        <Pin className="h-3 w-3" />
                      )}
                    </button>
                    <button
                      onClick={() => remove(n.id)}
                      className="rounded p-0.5 text-muted-foreground hover:text-red-400"
                      aria-label="delete note"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
                <p className="text-xs leading-relaxed text-foreground/90 whitespace-pre-wrap break-words">
                  {n.content}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}
