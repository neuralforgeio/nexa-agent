"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Role = "user" | "assistant";

interface ToolResult {
  tool: string;
  ok: boolean;
  output: string;
  duration_ms?: number;
  error?: string;
}

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  toolResults?: ToolResult[];
  thinking?: boolean;
  streaming?: boolean;
  createdAt: number;
}

interface SessionSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

// SSE event payloads from the Python backend
type SSEEvent =
  | { type: "session"; sessionId: string; isNew: boolean }
  | { type: "thinking" }
  | { type: "token"; text: string }
  | { type: "tool_result"; toolResult: ToolResult }
  | { type: "done"; answer: string }
  | { type: "error"; message?: string; error?: string }
  | { type: "end" };

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = "nexa-agent-ui";

const SUGGESTIONS = [
  "What time is it in Tokyo?",
  "Calculate (128 × 9) + 14.5",
  "Search the web for latest AI news",
  "List files in the workspace",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatSessionTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

/** Very small markdown-ish renderer (bold, code, code blocks, line breaks). */
function renderMarkdown(text: string): string {
  if (!text) return "";
  // Escape HTML first
  let out = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // Code blocks ```...```
  out = out.replace(
    /```(\w*)\n?([\s\S]*?)```/g,
    (_m, _lang, code) =>
      `<pre><code>${code.replace(/\n$/, "")}</code></pre>`
  );
  // Inline code `...`
  out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  // Bold **...**
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Headings
  out = out.replace(/^### (.*)$/gm, "<h3>$1</h3>");
  out = out.replace(/^## (.*)$/gm, "<h2>$1</h2>");
  out = out.replace(/^# (.*)$/gm, "<h1>$1</h1>");
  // Line breaks → paragraphs (simple)
  out = out
    .split(/\n{2,}/)
    .map((block) => {
      if (block.startsWith("<pre>") || block.startsWith("<h")) return block;
      return `<p>${block.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("");
  return out;
}

// ---------------------------------------------------------------------------
// Icon (inline SVG, lightweight)
// ---------------------------------------------------------------------------

function Icon({
  name,
  className = "",
}: {
  name: "send" | "plus" | "menu" | "close" | "trash" | "tool" | "user" | "spark";
  className?: string;
}) {
  const paths: Record<string, JSX.Element> = {
    send: (
      <path d="M3.4 20.4 21 12 3.4 3.6 3 10l12 2-12 2z" />
    ),
    plus: (
      <>
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </>
    ),
    menu: (
      <>
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="3" y1="18" x2="21" y2="18" />
      </>
    ),
    close: (
      <>
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </>
    ),
    trash: (
      <>
        <polyline points="3 6 5 6 21 6" />
        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
        <path d="M10 11v6M14 11v6" />
        <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      </>
    ),
    tool: (
      <>
        <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-.5-.5-2.5 2.5-2.5z" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 4-6 8-6s8 2 8 6" />
      </>
    ),
    spark: (
      <>
        <path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8z" />
      </>
    ),
  };
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Collapsible tool result card
// ---------------------------------------------------------------------------

function ToolCard({ result }: { result: ToolResult }) {
  const [open, setOpen] = useState(false);
  const ok = result.ok !== false;
  return (
    <div
      className="rounded-lg border my-2 overflow-hidden text-sm"
      style={{
        borderColor: ok ? "var(--border)" : "rgba(255,90,90,0.4)",
        background: "var(--accent-subtle)",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--bg-hover)] transition-colors"
        aria-expanded={open}
      >
        <Icon
          name="tool"
          className="w-4 h-4"
        />
        <span className="font-mono text-[13px] font-medium flex-1 truncate">
          {result.tool}
        </span>
        <span
          className="text-[11px] px-1.5 py-0.5 rounded font-mono"
          style={{
            background: ok ? "rgba(74,158,255,0.15)" : "rgba(255,90,90,0.15)",
            color: ok ? "var(--accent)" : "#FF6B6B",
          }}
        >
          {ok ? "ok" : "err"}
        </span>
        {typeof result.duration_ms === "number" && (
          <span className="text-[11px] text-[var(--fg-subtle)] font-mono">
            {result.duration_ms}ms
          </span>
        )}
        <span
          className="text-[var(--fg-subtle)] transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          ›
        </span>
      </button>
      {open && (
        <pre className="px-3 py-2 overflow-x-auto text-[12px] font-mono text-[var(--fg-muted)] border-t border-[var(--border)] max-h-64 overflow-y-auto">
          {result.error || result.output || "(no output)"}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageView({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end fade-in my-3">
        <div className="max-w-[85%] sm:max-w-[75%]">
          <div
            className="px-4 py-2.5 rounded-2xl rounded-br-md text-[15px] leading-relaxed"
            style={{
              background: "var(--bg-tertiary)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
          >
            {msg.content}
          </div>
          <div className="text-[11px] text-[var(--fg-subtle)] text-right mt-1 pr-1">
            {formatTime(msg.createdAt)}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3 my-4 fade-in">
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
        style={{ background: "var(--accent)", color: "#0F0F0F" }}
        aria-hidden="true"
      >
        <Icon name="spark" className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-[13px] font-semibold">Nexa</span>
          <span className="text-[11px] text-[var(--fg-subtle)]">
            {formatTime(msg.createdAt)}
          </span>
        </div>
        {msg.toolResults && msg.toolResults.length > 0 && (
          <div className="mb-2">
            {msg.toolResults.map((r, i) => (
              <ToolCard key={i} result={r} />
            ))}
          </div>
        )}
        {msg.thinking && !msg.content ? (
          <div className="flex items-center gap-1 py-1">
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="text-[13px] text-[var(--fg-muted)] ml-2">
              thinking…
            </span>
          </div>
        ) : (
          <div
            className="prose-chat text-[15px] leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(msg.content) + (msg.streaming ? '<span class="nexa-caret"></span>' : ""),
            }}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  sessions: SessionSummary[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose?: () => void;
}

function Sidebar({
  sessions,
  activeId,
  loading,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: SidebarProps) {
  return (
    <div className="flex flex-col h-full w-full" style={{ background: "var(--bg-secondary)" }}>
      {/* Brand header */}
      <div className="flex items-center gap-2 px-4 h-14 border-b border-[var(--border-subtle)]">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center"
          style={{ background: "var(--accent)", color: "#0F0F0F" }}
        >
          <Icon name="spark" className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <div className="text-[14px] font-semibold leading-tight">Nexa Agent</div>
          <div className="text-[11px] text-[var(--fg-subtle)] leading-tight">
            v1.6.0
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden p-1.5 rounded hover:bg-[var(--bg-hover)]"
            aria-label="Close sidebar"
          >
            <Icon name="close" className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* New chat */}
      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-[14px] font-medium transition-colors"
          style={{
            background: "var(--accent)",
            color: "#0F0F0F",
          }}
        >
          <Icon name="plus" className="w-4 h-4" />
          New chat
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        <div className="text-[11px] uppercase tracking-wider text-[var(--fg-subtle)] px-2 py-2">
          Conversations
        </div>
        {loading ? (
          <div className="px-2 py-4 text-[13px] text-[var(--fg-muted)]">
            Loading…
          </div>
        ) : sessions.length === 0 ? (
          <div className="px-2 py-4 text-[13px] text-[var(--fg-muted)]">
            No conversations yet.
          </div>
        ) : (
          <ul className="space-y-0.5">
            {sessions.map((s) => {
              const active = s.id === activeId;
              return (
                <li key={s.id}>
                  <div
                    className={`group flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${
                      active ? "" : "hover:bg-[var(--bg-hover)]"
                    }`}
                    style={
                      active
                        ? { background: "var(--accent-subtle)" }
                        : undefined
                    }
                    onClick={() => onSelect(s.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-[13px] truncate"
                        style={{
                          color: active ? "var(--accent)" : "var(--fg)",
                          fontWeight: active ? 500 : 400,
                        }}
                      >
                        {s.title || "Untitled"}
                      </div>
                      <div className="text-[11px] text-[var(--fg-subtle)] flex items-center gap-1.5">
                        <span>{formatSessionTime(s.updatedAt || s.createdAt)}</span>
                        <span>·</span>
                        <span>{s.messageCount} msg</span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(s.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--bg-tertiary)] text-[var(--fg-muted)] hover:text-red-400 transition-opacity"
                      aria-label="Delete conversation"
                    >
                      <Icon name="trash" className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="px-4 py-3 border-t border-[var(--border-subtle)] text-[11px] text-[var(--fg-subtle)]">
        © 2026 Nexa Agent · MIT
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Page() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const assistantBufferRef = useRef<ChatMessage | null>(null);

  // ---- Sessions -----------------------------------------------------------

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await fetch("/api/sessions", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSessions(Array.isArray(data.sessions) ? data.sessions : []);
    } catch (e) {
      console.warn("Failed to load sessions:", e);
      setSessions([]);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // ---- Auto-scroll on new messages ---------------------------------------

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ---- Textarea auto-grow -------------------------------------------------

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  // ---- SSE parser ---------------------------------------------------------

  const handleSSE = useCallback(
    async (reader: ReadableStreamDefaultReader<Uint8Array>) => {
      const decoder = new TextDecoder();
      let buffer = "";
      let finalAnswer = "";
      const toolResults: ToolResult[] = [];

      const ensureAssistant = (): ChatMessage => {
        if (!assistantBufferRef.current) {
          assistantBufferRef.current = {
            id: uid(),
            role: "assistant",
            content: "",
            thinking: false,
            streaming: true,
            createdAt: Date.now(),
          };
          setMessages((prev) => [...prev, assistantBufferRef.current!]);
        }
        return assistantBufferRef.current;
      };

      const patch = (mut: (m: ChatMessage) => ChatMessage) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantBufferRef.current?.id ? mut({ ...m }) : m
          )
        );
      };

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          // Each event may have multiple lines; we want `data:` lines
          const dataLines = rawEvent
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trim());
          if (dataLines.length === 0) continue;
          const dataStr = dataLines.join("\n");
          if (!dataStr || dataStr === "[DONE]") continue;

          let evt: SSEEvent | null = null;
          try {
            evt = JSON.parse(dataStr) as SSEEvent;
          } catch {
            continue;
          }
          if (!evt) continue;

          switch (evt.type) {
            case "session": {
              if (evt.sessionId) {
                setActiveId(evt.sessionId);
              }
              break;
            }
            case "thinking": {
              ensureAssistant();
              patch((m) => ({ ...m, thinking: true }));
              break;
            }
            case "token": {
              ensureAssistant();
              finalAnswer += evt.text;
              patch((m) => ({
                ...m,
                thinking: false,
                content: m.content + evt.text,
              }));
              break;
            }
            case "tool_result": {
              ensureAssistant();
              if (evt.toolResult) {
                toolResults.push(evt.toolResult);
                patch((m) => ({
                  ...m,
                  thinking: false,
                  toolResults: [...(m.toolResults || []), evt.toolResult],
                }));
              }
              break;
            }
            case "done": {
              if (evt.answer != null) finalAnswer = evt.answer;
              patch((m) => ({
                ...m,
                content: evt.answer != null ? evt.answer : m.content,
                thinking: false,
              }));
              break;
            }
            case "error": {
              const msg = evt.message || evt.error || "Unknown error";
              patch((m) => ({
                ...m,
                content: m.content
                  ? m.content + `\n\n**Error:** ${msg}`
                  : `**Error:** ${msg}`,
                thinking: false,
              }));
              setError(msg);
              break;
            }
            case "end": {
              // finalize
              patch((m) => ({
                ...m,
                streaming: false,
                thinking: false,
              }));
              break;
            }
          }
        }
      }

      // Final ensure streaming flag off
      patch((m) => ({ ...m, streaming: false, thinking: false }));
      return { finalAnswer, toolResults };
    },
    []
  );

  // ---- Persist after stream completes ------------------------------------

  const persistTurn = useCallback(
    async (
      sessionId: string | null,
      userMessage: string,
      assistantAnswer: string,
      toolResults: ToolResult[]
    ) => {
      try {
        await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "persist",
            sessionId: sessionId || undefined,
            userMessage,
            assistantAnswer,
            toolResults: toolResults.map((t) => ({
              tool: t.tool,
              ok: t.ok,
              output: t.output,
              duration_ms: t.duration_ms,
              error: t.error,
            })),
          }),
        });
        // Refresh sessions list to reflect updated message count / title
        loadSessions();
      } catch (e) {
        console.warn("Persist failed:", e);
      }
    },
    [loadSessions]
  );

  // ---- Send a message -----------------------------------------------------

  const send = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || sending) return;

      setError(null);
      setInput("");

      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content,
        createdAt: Date.now(),
      };
      assistantBufferRef.current = null;
      setMessages((prev) => [...prev, userMsg]);
      setSending(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const capturedSessionId = activeId;
      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify({
            message: content,
            sessionId: activeId || undefined,
          }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          const errText = await res.text().catch(() => "");
          throw new Error(
            `Stream request failed (HTTP ${res.status}) ${errText.slice(0, 200)}`
          );
        }

        // Hook a one-time capture for session events to update capturedSessionId
        const originalReader = res.body.getReader();
        const { finalAnswer, toolResults } = await handleSSE(originalReader);

        // The handleSSE sets activeId via patch, but capture it again to be safe
        // (activeId state may not be flushed yet.)
        // Persist after completion.
        await persistTurn(
          activeId || capturedSessionId,
          content,
          finalAnswer,
          toolResults
        );
      } catch (e) {
        const err = e as Error;
        if (err.name === "AbortError") {
          // user cancelled
        } else {
          console.error("Send failed:", err);
          setError(err.message || "Failed to send message");
          // Add an assistant error message if none was started
          if (!assistantBufferRef.current) {
            const errMsg: ChatMessage = {
              id: uid(),
              role: "assistant",
              content: `**Error:** ${err.message || "Failed to send message"}`,
              createdAt: Date.now(),
            };
            setMessages((prev) => [...prev, errMsg]);
          }
        }
      } finally {
        setSending(false);
        abortRef.current = null;
        assistantBufferRef.current = null;
        // refresh sessions (in case a new one was created server-side)
        loadSessions();
      }
    },
    [input, sending, activeId, handleSSE, persistTurn, loadSessions]
  );

  // ---- New chat -----------------------------------------------------------

  const newChat = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setActiveId(null);
    setMessages([]);
    setError(null);
    setInput("");
    setSidebarOpen(false);
  }, []);

  // ---- Select session -----------------------------------------------------

  const selectSession = useCallback(async (id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
    setError(null);
    try {
      const res = await fetch(`/api/sessions/${id}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Normalize to ChatMessage[]
      const msgs: ChatMessage[] = [];
      const rawMsgs: any[] = Array.isArray(data.messages) ? data.messages : [];
      let pendingAssistant: ChatMessage | null = null;
      for (const m of rawMsgs) {
        const role: Role = m.role === "user" ? "user" : "assistant";
        if (role === "user") {
          if (pendingAssistant) {
            msgs.push(pendingAssistant);
            pendingAssistant = null;
          }
          msgs.push({
            id: uid(),
            role: "user",
            content: m.content || "",
            createdAt: m.createdAt ? new Date(m.createdAt).getTime() : Date.now(),
          });
        } else {
          // assistant — collect any preceding tool messages into this assistant bubble
          const tools: ToolResult[] = [];
          if (pendingAssistant) {
            msgs.push(pendingAssistant);
            pendingAssistant = null;
          }
          pendingAssistant = {
            id: uid(),
            role: "assistant",
            content: m.content || "",
            toolResults: tools,
            createdAt: m.createdAt ? new Date(m.createdAt).getTime() : Date.now(),
          };
        }
      }
      if (pendingAssistant) msgs.push(pendingAssistant);
      setMessages(msgs);
    } catch (e) {
      console.warn("Failed to load session messages:", e);
      setMessages([]);
    }
  }, []);

  // ---- Delete session -----------------------------------------------------

  const deleteSession = useCallback(
    async (id: string) => {
      try {
        await fetch(`/api/sessions/${id}`, { method: "DELETE" });
        if (activeId === id) {
          setActiveId(null);
          setMessages([]);
        }
        loadSessions();
      } catch (e) {
        console.warn("Failed to delete session:", e);
      }
    },
    [activeId, loadSessions]
  );

  // ---- Keyboard handling --------------------------------------------------

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // ---- Suggestion click ---------------------------------------------------

  const onSuggestion = (text: string) => {
    setInput(text);
    textareaRef.current?.focus();
  };

  const isEmpty = messages.length === 0;

  // Memoized header title
  const headerTitle = useMemo(() => {
    if (activeId) {
      const s = sessions.find((x) => x.id === activeId);
      return s?.title || "New conversation";
    }
    return "New conversation";
  }, [activeId, sessions]);

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {/* Sidebar — desktop */}
      <aside className="hidden md:flex md:w-[260px] md:flex-shrink-0 border-r border-[var(--border-subtle)]">
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          loading={sessionsLoading}
          onSelect={selectSession}
          onNew={newChat}
          onDelete={deleteSession}
        />
      </aside>

      {/* Sidebar — mobile drawer */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <div className="relative w-[280px] max-w-[80vw] h-full shadow-2xl">
            <Sidebar
              sessions={sessions}
              activeId={activeId}
              loading={sessionsLoading}
              onSelect={selectSession}
              onNew={newChat}
              onDelete={deleteSession}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0 h-full">
        {/* Header */}
        <header className="flex items-center gap-3 h-14 px-4 border-b border-[var(--border-subtle)] flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-1.5 rounded hover:bg-[var(--bg-hover)]"
            aria-label="Open sidebar"
          >
            <Icon name="menu" className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-[14px] font-medium truncate">
              {headerTitle}
            </div>
            <div className="text-[11px] text-[var(--fg-subtle)] truncate">
              {sending ? "Nexa is responding…" : "Ready"}
            </div>
          </div>
          <button
            onClick={newChat}
            className="md:hidden p-1.5 rounded hover:bg-[var(--bg-hover)]"
            aria-label="New chat"
          >
            <Icon name="plus" className="w-5 h-5" />
          </button>
        </header>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto"
          style={{ scrollBehavior: "smooth" }}
        >
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4">
            {isEmpty ? (
              <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
                  style={{ background: "var(--accent)", color: "#0F0F0F" }}
                >
                  <Icon name="spark" className="w-7 h-7" />
                </div>
                <h1 className="text-2xl font-semibold mb-2">
                  Hello, I&apos;m Nexa
                </h1>
                <p className="text-[15px] text-[var(--fg-muted)] max-w-md mb-8">
                  An advanced AI agent with tool-calling, memory, and streaming.
                  Ask me anything to get started.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => onSuggestion(s)}
                      className="text-left px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors text-[13px] text-[var(--fg)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => <MessageView key={m.id} msg={m} />)
            )}
            {error && (
              <div
                className="mt-4 px-4 py-3 rounded-lg text-[13px] border"
                style={{
                  background: "rgba(255,90,90,0.08)",
                  borderColor: "rgba(255,90,90,0.3)",
                  color: "#FF8B8B",
                }}
              >
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="flex-shrink-0 border-t border-[var(--border-subtle)] bg-[var(--bg-primary)]">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3">
            <div
              className="flex items-end gap-2 rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] px-3 py-2 focus-within:border-[var(--accent)] transition-colors"
            >
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Message Nexa…"
                rows={1}
                disabled={sending}
                className="flex-1 bg-transparent border-0 outline-none resize-none text-[15px] leading-relaxed py-1.5 placeholder:text-[var(--fg-subtle)] disabled:opacity-60"
                style={{ color: "var(--fg)", maxHeight: 200 }}
                aria-label="Message input"
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || sending}
                className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  background: input.trim() ? "var(--accent)" : "var(--bg-tertiary)",
                  color: input.trim() ? "#0F0F0F" : "var(--fg-muted)",
                }}
                aria-label="Send message"
              >
                {sending ? (
                  <svg
                    className="w-4 h-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeOpacity="0.25"
                    />
                    <path
                      d="M12 2a10 10 0 0 1 10 10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />
                  </svg>
                ) : (
                  <Icon name="send" className="w-4 h-4" />
                )}
              </button>
            </div>
            <div className="text-[11px] text-[var(--fg-subtle)] text-center mt-2">
              Nexa can make mistakes. Press Enter to send, Shift+Enter for newline.
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
