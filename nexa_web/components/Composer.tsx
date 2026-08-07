/**
 * Nexa Agent — Composer Component
 *
 * Pill-shaped input with auto-grow textarea, send/stop button,
 * suggestion chips for the empty state, and file attachments.
 *
 * v4.7.0 (F-01): Stop button — aborts the active SSE stream via onStop.
 * v4.7.0 (F-11): file upload — paperclip picker, drag-and-drop, and image
 *   paste. Files upload to POST /api/upload; an "[Attached: <path>]" token
 *   is appended to the outgoing message so the agent can reference them.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Loader2, Square, Paperclip, X } from "lucide-react";

interface ComposerProps {
  onSend: (text: string) => void;
  /** F-01: invoked when the user clicks the Stop button during streaming. */
  onStop: () => void;
  disabled: boolean;
  /** True while a chat request is in flight (streaming). */
  thinking: boolean;
  showSuggestions: boolean;
}

interface Attachment {
  name: string;
  path: string;
  /** Object URL preview for image attachments. */
  preview?: string;
}

const SUGGESTIONS: Array<{ label: string; prompt: string }> = [
  { label: "💻 Write Code",       prompt: "Write a Python function that computes the nth Fibonacci number using constant space." },
  { label: "🖥 Run Terminal",     prompt: "Show me the contents of the current workspace using the terminal." },
  { label: "🔍 Search Web",       prompt: "Search the web for the latest AI news and summarize the top 3 stories." },
  { label: "📄 Analyze File",     prompt: "Read README.md in this repository and summarize what this project does." },
];

export function Composer({ onSend, onStop, disabled, thinking, showSuggestions }: ComposerProps) {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  // F-11: upload one File to the backend, add to the attachment list.
  const uploadFile = async (file: File) => {
    if (!file || uploading) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      if (!res.ok) return; // surface nothing — keep silent to avoid noisy alerts
      const data = (await res.json()) as { filename?: string; path?: string };
      if (!data.path) return;
      setAttachments((a) => [
        ...a,
        {
          name: data.filename ?? file.name,
          path: data.path!,
          preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
        },
      ]);
    } catch {
      /* upload failed — leave the composer usable */
    } finally {
      setUploading(false);
    }
  };

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    for (const f of Array.from(e.target.files ?? [])) void uploadFile(f);
    e.target.value = "";
  };

  // F-11: drag-and-drop.
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    for (const f of Array.from(e.dataTransfer.files ?? [])) void uploadFile(f);
  };
  const onDragOver = (e: React.DragEvent) => {
    if (e.dataTransfer.types.includes("Files")) {
      e.preventDefault();
      setDragging(true);
    }
  };

  // F-11: paste an image (screenshot) straight into the composer.
  const onPaste = (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData?.items ?? []);
    for (const it of items) {
      if (it.kind === "file") {
        const f = it.getAsFile();
        if (f) {
          e.preventDefault();
          void uploadFile(f);
        }
      }
    }
  };

  const submit = () => {
    const text = value.trim();
    if ((!text && attachments.length === 0) || disabled) return;
    const suffix = attachments.length
      ? "\n\n" + attachments.map((a) => `[Attached: ${a.path}]`).join("\n")
      : "";
    onSend(text + suffix);
    setValue("");
    setAttachments((a) => {
      for (const att of a) if (att.preview) URL.revokeObjectURL(att.preview);
      return [];
    });
  };

  const removeAttachment = (idx: number) =>
    setAttachments((a) => {
      const copy = [...a];
      const [gone] = copy.splice(idx, 1);
      if (gone?.preview) URL.revokeObjectURL(gone.preview);
      return copy;
    });

  const streaming = thinking;
  const sendDisabled = disabled || (!value.trim() && attachments.length === 0);
  const buttonDisabled = streaming ? false : sendDisabled;
  const canSend = value.trim().length > 0 || attachments.length > 0;

  return (
    <div
      style={{ background: "linear-gradient(to top, var(--nexa-surface, #141618), transparent)", padding: "0 16px 16px" }}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={() => setDragging(false)}
    >
      <div style={{ maxWidth: 768, margin: "0 auto" }}>
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

        {/* F-11: attached files */}
        {attachments.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }} data-testid="attachments">
            {attachments.map((a, i) => (
              <div
                key={a.path + i}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  border: "1px solid #2E2F34", background: "#191B1E",
                  borderRadius: 8, padding: "4px 8px", fontSize: 12, color: "#CFCFCF",
                }}
              >
                {a.preview ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={a.preview} alt={a.name} style={{ width: 28, height: 28, objectFit: "cover", borderRadius: 4 }} />
                ) : (
                  <Paperclip size={12} color="#8F8F8F" />
                )}
                <span style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.name}</span>
                <button
                  aria-label={`remove-${a.name}`}
                  onClick={() => removeAttachment(i)}
                  style={{ background: "transparent", border: "none", cursor: "pointer", color: "#8F8F8F", display: "flex" }}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Input */}
        <div
          style={{
            display: "flex", alignItems: "flex-end", gap: 8,
            borderRadius: 24, border: `1px solid ${dragging ? "#4A9EFF" : "#2E2F34"}`, background: "#222327",
            padding: "8px 8px 8px 16px", transition: "border-color 0.15s",
            boxShadow: dragging ? "0 0 0 2px rgba(74,158,255,0.25)" : undefined,
          }}
        >
          {/* F-11: hidden file input + paperclip */}
          <input
            ref={fileRef}
            type="file"
            multiple
            style={{ display: "none" }}
            data-testid="file-input"
            onChange={onPickFiles}
          />
          <button
            type="button"
            aria-label="attach-files"
            title="Attach files"
            onClick={() => fileRef.current?.click()}
            disabled={disabled}
            style={{
              width: 30, height: 30, flexShrink: 0, borderRadius: "50%",
              border: "1px solid transparent", background: "transparent",
              color: "#9A9A9A", cursor: disabled ? "not-allowed" : "pointer", display: "flex",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <Paperclip size={16} />
          </button>

          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            onPaste={onPaste}
            placeholder={dragging ? "Drop files to attach…" : "Ask Nexa anything…"}
            rows={1}
            disabled={disabled}
            style={{
              flex: 1, resize: "none", background: "transparent", border: "none",
              color: "#ECECEC", fontSize: 15, lineHeight: 1.6, fontFamily: "inherit",
              outline: "none", maxHeight: 200, opacity: disabled ? 0.5 : 1,
            }}
          />
          <button
            type="button"
            data-testid={streaming ? "stop-button" : "send-button"}
            aria-label={streaming ? "Stop generating" : "Send message"}
            onClick={() => (streaming ? onStop() : submit())}
            disabled={buttonDisabled}
            style={
              streaming
                ? {
                    width: 32, height: 32, flexShrink: 0, borderRadius: "50%",
                    border: "1px solid rgba(248, 113, 113, 0.55)",
                    background: "rgba(248, 113, 113, 0.18)",
                    color: "#F87171", cursor: "pointer", display: "flex",
                    alignItems: "center", justifyContent: "center",
                    transition: "background 0.15s, opacity 0.15s",
                  }
                : {
                    width: 32, height: 32, flexShrink: 0, borderRadius: "50%",
                    border: "1px solid rgba(74, 158, 255, 0.4)",
                    background: "rgba(74, 158, 255, 0.15)",
                    color: "#4A9EFF", cursor: "pointer", display: "flex",
                    alignItems: "center", justifyContent: "center",
                    opacity: buttonDisabled ? 0.3 : 1, transition: "opacity 0.15s",
                  }
            }
          >
            {streaming ? (
              <Square size={14} fill="currentColor" data-testid="stop-icon" />
            ) : thinking || uploading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <ArrowUp size={18} />
            )}
          </button>
        </div>
        <div style={{ textAlign: "center", fontSize: 11, color: "#6A6A6A", marginTop: 8 }}>
          Nexa can make mistakes. Verify important info.{canSend ? "" : " Drop files here to attach."}
        </div>
      </div>
    </div>
  );
}
