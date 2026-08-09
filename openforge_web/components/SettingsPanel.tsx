/**
 * OpenForge — Settings Panel (v4.1.0)
 *
 * Modal dialog for managing LLM providers:
 *   - List all providers (catalog + custom).
 *   - Add a new provider (name, base_url, api_key, model).
 *   - Activate a provider (hot-swaps the live agent).
 *   - Remove a custom provider.
 *   - Test a provider's health (200 OK check).
 *
 * Talks to the Python backend via:
 *   GET    /api/provider         (list)
 *   POST   /api/provider         (add/update)
 *   DELETE /api/provider         (remove)
 *   POST   /api/provider/use     (activate)
 *   POST   /api/provider/test    (health-check)
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

"use client";

import { useEffect, useRef, useState } from "react";
import {
  Settings, X, Plus, Trash2, Zap, CheckCircle2, XCircle, Loader2,
  Search, ChevronDown, ChevronUp, Play,
} from "lucide-react";

interface ProviderEntry {
  name: string;
  base_url: string;
  model: string;
  api_key: string; // masked (e.g. "tr_...wxyz") or "(env)"
  is_active: boolean;
}

interface ProviderListResponse {
  active: string | null;
  providers: ProviderEntry[];
}

interface SkillCard {
  name: string;
  version: string;
  description: string;
  category: string;
  author: string;
  permissions: string[];
  tags: string[];
  examples: { input: Record<string, unknown> }[];
  enabled: boolean;
}

type PanelTab = "providers" | "skills";

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [activeName, setActiveName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<Record<string, "idle" | "testing" | "ok" | "fail">>({});

  // Skills tab state.
  const [tab, setTab] = useState<PanelTab>("providers");
  const [skills, setSkills] = useState<SkillCard[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsError, setSkillsError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [executingSkill, setExecutingSkill] = useState<Record<string, "idle" | "running" | "ok" | "fail">>({});
  const [skillResults, setSkillResults] = useState<Record<string, unknown>>({});
  const [searchQuery, setSearchQuery] = useState("");

  // F-09: dialog behaviour (Esc to close, focus trap, body scroll-lock,
  // focus restoration on close).
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    openerRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // scroll-lock
    // Initial focus into the dialog.
    const el = panelRef.current;
    const focusables = el?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    (focusables && focusables.length > 0 ? focusables[0] : el)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === "Tab" && el) {
        // Focus-trap: keep Tab / Shift+Tab cycling inside the panel.
        const items = Array.from(
          el.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          )
        ).filter((n) => !n.hasAttribute("disabled") && n.tabIndex !== -1);
        if (items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (e.shiftKey) {
          if (active === first || !el.contains(active)) {
            e.preventDefault();
            last.focus();
          }
        } else if (active === last || !el.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", onKey, true);
      // Restore focus to whatever opened the dialog.
      openerRef.current?.focus?.();
    };
  }, []);

  const SKILL_CATEGORIES = [
    "code_intelligence",
    "web_research",
    "creative_media",
    "communication",
    "data_analytics",
    "devops_operations",
  ];

  const CATEGORY_LABELS: Record<string, string> = {
    code_intelligence: "Code Intelligence",
    web_research: "Web & Research",
    creative_media: "Creative & Media",
    communication: "Communication",
    data_analytics: "Data & Analytics",
    devops_operations: "DevOps & Operations",
  };

  // Add-form state.
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newBaseUrl, setNewBaseUrl] = useState("");
  const [newApiKey, setNewApiKey] = useState("");
  const [newModel, setNewModel] = useState("");
  const [activateOnAdd, setActivateOnAdd] = useState(true);
  const [addError, setAddError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/provider", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as ProviderListResponse;
      setProviders(data.providers);
      setActiveName(data.active);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load providers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleUse = async (name: string) => {
    try {
      const res = await fetch("/api/provider/use", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate provider");
    }
  };

  const handleRemove = async (name: string) => {
    if (!confirm(`Remove provider "${name}"?`)) return;
    try {
      const res = await fetch("/api/provider", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove provider");
    }
  };

  const handleTest = async (name: string) => {
    setTestStatus((s) => ({ ...s, [name]: "testing" }));
    try {
      const res = await fetch("/api/provider/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = (await res.json()) as { ok: boolean };
      setTestStatus((s) => ({ ...s, [name]: data.ok ? "ok" : "fail" }));
    } catch {
      setTestStatus((s) => ({ ...s, [name]: "fail" }));
    }
  };

  // -------------------------------------------------------------------
  // Skills helpers
  // -------------------------------------------------------------------
  const loadSkills = async () => {
    setSkillsLoading(true);
    setSkillsError(null);
    try {
      const res = await fetch("/api/skills", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { skills: SkillCard[] };
      setSkills(data.skills);
    } catch (err) {
      setSkillsError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setSkillsLoading(false);
    }
  };

  const handleExecuteSkill = async (name: string, input: Record<string, unknown>) => {
    setExecutingSkill((s) => ({ ...s, [name]: "running" }));
    try {
      const res = await fetch(`/api/skills/${name}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input }),
      });
      const data = (await res.json()) as { ok: boolean; result?: unknown; error?: string };
      if (data.ok) {
        setSkillResults((s) => ({ ...s, [name]: data.result }));
        setExecutingSkill((s) => ({ ...s, [name]: "ok" }));
      } else {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
    } catch {
      setExecutingSkill((s) => ({ ...s, [name]: "fail" }));
    }
  };

  const filteredSkills = skills.filter((s) => {
    const matchCategory = !selectedCategory || s.category === selectedCategory;
    const matchQuery =
      !searchQuery ||
      s.name.includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchCategory && matchQuery;
  });

  const handleAdd = async () => {
    setAddError(null);
    if (!newName.trim() || !newBaseUrl.trim()) {
      setAddError("Name and Base URL are required.");
      return;
    }
    try {
      const res = await fetch("/api/provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName.trim(),
          base_url: newBaseUrl.trim(),
          api_key: newApiKey.trim(),
          model: newModel.trim(),
          activate: activateOnAdd,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      // Reset form.
      setNewName("");
      setNewBaseUrl("");
      setNewApiKey("");
      setNewModel("");
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add provider");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.7)",
      }}
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Provider and skills settings"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(640px, 92vw)",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "#1A1B1E",
          border: "1px solid #2E2F34",
          borderRadius: 12,
          padding: 24,
          outline: "none",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "#ECECEC" }}>
            <Settings size={18} style={{ verticalAlign: "middle", marginRight: 8, color: "#4A9EFF" }} />
            LLM Providers
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{ background: "transparent", border: "none", color: "#9A9A9A", cursor: "pointer" }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab bar */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #2E2F34" }}>
          {(["providers", "skills"] as PanelTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: "6px 16px",
                background: "transparent",
                border: "none",
                borderBottom: tab === t ? "2px solid #4A9EFF" : "2px solid transparent",
                color: tab === t ? "#4A9EFF" : "#9A9A9A",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: tab === t ? 600 : 400,
                marginBottom: -1,
              }}
            >
              {t === "providers" ? "Providers" : "Skills"}
            </button>
          ))}
        </div>

        {tab === "providers" && (
          <>
            {error && (
              <div style={{ padding: "8px 12px", marginBottom: 12, background: "rgba(248,113,113,0.12)", borderRadius: 6, color: "#F87171", fontSize: 13 }}>
                {error}
              </div>
            )}
            {/* Provider list — existing */}
            {loading ? (
              <div style={{ textAlign: "center", padding: 24, color: "#9A9A9A" }}>Loading...</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
            {providers.map((p) => {
              const status = testStatus[p.name] || "idle";
              return (
                <div
                  key={p.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 12px",
                    background: p.is_active ? "rgba(74,158,255,0.08)" : "#141618",
                    border: `1px solid ${p.is_active ? "#4A9EFF" : "#2E2F34"}`,
                    borderRadius: 8,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontWeight: 600, color: "#ECECEC" }}>{p.name}</span>
                      {p.is_active && (
                        <span style={{ fontSize: 10, padding: "2px 6px", background: "#4A9EFF", color: "#fff", borderRadius: 999 }}>
                          ACTIVE
                        </span>
                      )}
                      {status === "ok" && <CheckCircle2 size={14} color="#4ADE80" />}
                      {status === "fail" && <XCircle size={14} color="#F87171" />}
                      {status === "testing" && <Loader2 size={14} color="#9A9A9A" className="animate-spin" />}
                    </div>
                    <div style={{ fontSize: 12, color: "#9A9A9A", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {p.base_url || "(set NEXA_BASE_URL)"} · {p.model || "(default)"} · {p.api_key || "(env)"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    {!p.is_active && (
                      <button
                        onClick={() => handleUse(p.name)}
                        style={btnStyle}
                        title="Activate"
                      >
                        <Zap size={14} />
                      </button>
                    )}
                    <button onClick={() => handleTest(p.name)} style={btnStyle} title="Test">
                      Test
                    </button>
                    <button
                      onClick={() => handleRemove(p.name)}
                      style={{ ...btnStyle, color: "#F87171" }}
                      title="Remove"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Add new provider form */}
        {showAdd ? (
          <div style={{ padding: 16, background: "#141618", border: "1px solid #2E2F34", borderRadius: 8, marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#ECECEC", marginBottom: 12 }}>Add Provider</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
              <input style={inputStyle} placeholder="Name (e.g. tokenrouter)" value={newName} onChange={(e) => setNewName(e.target.value)} />
              <input style={inputStyle} placeholder="Model (e.g. auto:balance)" value={newModel} onChange={(e) => setNewModel(e.target.value)} />
            </div>
            <input style={{ ...inputStyle, marginBottom: 8, width: "100%" }} placeholder="Base URL (https://api.tokenrouter.io/v1)" value={newBaseUrl} onChange={(e) => setNewBaseUrl(e.target.value)} />
            <input style={{ ...inputStyle, marginBottom: 8, width: "100%" }} type="password" placeholder="API key (tr_...)" value={newApiKey} onChange={(e) => setNewApiKey(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#9A9A9A", marginBottom: 12 }}>
              <input type="checkbox" checked={activateOnAdd} onChange={(e) => setActivateOnAdd(e.target.checked)} />
              Activate immediately
            </label>
            {addError && <div style={{ color: "#F87171", fontSize: 12, marginBottom: 8 }}>{addError}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={handleAdd} style={primaryBtnStyle}>Add</button>
              <button onClick={() => setShowAdd(false)} style={btnStyle}>Cancel</button>
            </div>
          </div>
        ) : (
            <button
              onClick={() => setShowAdd(true)}
              style={{ ...primaryBtnStyle, width: "100%" }}
            >
              <Plus size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
              Add Provider
            </button>
          )}

          <div style={{ marginTop: 16, fontSize: 11, color: "#6A6A6A", textAlign: "center" }}>
            API keys are stored in ~/.openforge/secrets/providers.json (chmod 600).
          </div>
        </>
      )}

      {/* ── SKILLS TAB ─────────────────────────────────────────── */}
      {tab === "skills" && <SkillsView />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skills sub-view
// ---------------------------------------------------------------------------

interface SkillRowProps {
  skill: SkillCard;
  executing: Record<string, string>;
  results: Record<string, unknown>;
  onToggle: (name: string) => void;
  onExecute: (name: string, input: Record<string, unknown>) => void;
}

function SkillRow({ skill, executing, results, onToggle, onExecute }: SkillRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [inputJson, setInputJson] = useState("");
  const status = executing[skill.name] || "idle";
  const example = skill.examples?.[0]?.input || {};

  return (
    <div
      style={{
        padding: "10px 12px",
        background: skill.enabled === false ? "#0F1012" : "#141618",
        border: `1px solid ${skill.enabled === false ? "#2E2F3444" : "#2E2F34"}`,
        borderRadius: 8,
        marginBottom: 8,
        opacity: skill.enabled === false ? 0.6 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <code style={{ color: "#4A9EFF", fontSize: 13 }}>{skill.name}</code>
            <span
              style={{
                fontSize: 10,
                padding: "1px 6px",
                background: skill.enabled === false ? "#374151" : "#1D4ED822",
                color: skill.enabled === false ? "#9CA3AF" : "#60A5FA",
                border: `1px solid ${skill.enabled === false ? "#4B5563" : "#1D4ED855"}`,
                borderRadius: 999,
              }}
            >
              {skill.enabled === false ? "disabled" : skill.category}
            </span>
            {status === "running" && <Loader2 size={12} color="#9CA3AF" className="animate-spin" />}
            {status === "ok" && <CheckCircle2 size={12} color="#4ADE80" />}
            {status === "fail" && <XCircle size={12} color="#F87171" />}
          </div>
          <div style={{ fontSize: 12, color: "#9CA3AF", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {skill.description}
          </div>
        </div>

        <div style={{ display: "flex", gap: 4, alignItems: "center", flexShrink: 0 }}>
          {expanded ? (
            <button style={btnStyle} onClick={() => setExpanded(false)} title="Collapse">
              <ChevronUp size={12} />
            </button>
          ) : (
            <button style={btnStyle} onClick={() => setExpanded(true)} title="Expand manifest">
              <ChevronDown size={12} />
            </button>
          )}
          <button
            style={{ ...primaryBtnStyle, padding: "4px 10px", fontSize: 11 }}
            title="Execute with example input"
            disabled={status === "running"}
            onClick={() => {
              let payload: Record<string, unknown> = {};
              if (Object.keys(example).length) payload = example;
              else if (inputJson.trim()) {
                try { payload = JSON.parse(inputJson); } catch { }
              }
              onExecute(skill.name, payload);
            }}
          >
            <Play size={11} />
          </button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, padding: "10px", background: "#0F1012", borderRadius: 6, fontSize: 11, color: "#9CA3AF" }}>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: "#ECECEC", fontWeight: 600 }}>Permissions:</span>{" "}
            {skill.permissions.join(", ") || "none"}
          </div>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: "#ECECEC", fontWeight: 600 }}>Tags:</span>{" "}
            {skill.tags.join(", ") || "none"}
          </div>
          {skill.examples?.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ color: "#ECECEC", fontWeight: 600 }}>Example input:</span>
              <textarea
                style={{
                  display: "block", width: "100%", marginTop: 4, padding: 6,
                  background: "#141618", border: "1px solid #2E2F34", borderRadius: 4,
                  color: "#ECECEC", fontSize: 11, fontFamily: "monospace",
                  resize: "vertical", minHeight: 60,
                }}
                defaultValue={JSON.stringify(example, null, 2)}
                onChange={(e) => setInputJson(e.target.value)}
              />
            </div>
          )}
          {results[skill.name] !== undefined && (
            <div style={{ marginTop: 8, padding: 6, background: "#1A291E", borderRadius: 4, color: "#86EFAC" }}>
              <pre style={{ margin: 0, overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {typeof results[skill.name] === "string"
                  ? results[skill.name] as string
                  : JSON.stringify(results[skill.name], null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SkillsView() {
  const [skills, setSkills] = useState<SkillCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [executing, setExecuting] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, unknown>>({});

  const SKILL_CATEGORIES = [
    "code_intelligence", "web_research", "creative_media",
    "communication", "data_analytics", "devops_operations",
  ];

  const CATEGORY_LABELS: Record<string, string> = {
    code_intelligence: "Code Intel",
    web_research: "Web Research",
    creative_media: "Creative",
    communication: "Comms",
    data_analytics: "Data",
    devops_operations: "DevOps",
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/skills", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { skills: SkillCard[] };
        setSkills(data.skills);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load skills");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleExecute = async (name: string, input: Record<string, unknown>) => {
    setExecuting((s) => ({ ...s, [name]: "running" }));
    try {
      const res = await fetch(`/api/skills/${name}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input }),
      });
      const data = (await res.json()) as { ok: boolean; result?: unknown; error?: string };
      if (data.ok) {
        setResults((s) => ({ ...s, [name]: data.result }));
        setExecuting((s) => ({ ...s, [name]: "ok" }));
      } else {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
    } catch (err) {
      setExecuting((s) => ({ ...s, [name]: "fail" }));
      setResults((s) => ({
        ...s,
        [name]: (err instanceof Error ? err.message : String(err)),
      }));
    }
  };

  const filtered = skills.filter((s) => {
    const matchCategory = !selectedCategory || s.category === selectedCategory;
    const matchQuery =
      !searchQuery ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.tags.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchCategory && matchQuery;
  });

  const groupedCategoryCounts = SKILL_CATEGORIES.reduce((acc, cat) => {
    acc[cat] = filtered.filter((s) => s.category === cat).length;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div>
      {error && (
        <div style={{ padding: "8px 12px", marginBottom: 12, background: "rgba(248,113,113,0.12)", borderRadius: 6, color: "#F87171", fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Search + category filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={13} style={{ position: "absolute", left: 8, top: "50%", transform: "translateY(-50%)", color: "#6B7280" }} />
          <input
            style={{ ...inputStyle, paddingLeft: 26, width: "100%", fontSize: 12 }}
            placeholder="Search skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Category chips */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        <button
          onClick={() => setSelectedCategory(null)}
          style={{
            padding: "3px 10px", fontSize: 11, borderRadius: 999, cursor: "pointer",
            background: selectedCategory === null ? "#1D4ED8" : "#2A2B30",
            border: "1px solid #2E2F34",
            color: selectedCategory === null ? "#fff" : "#9CA3AF",
          }}
        >
          All
        </button>
        {SKILL_CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
            style={{
              padding: "3px 10px", fontSize: 11, borderRadius: 999, cursor: "pointer",
              background: selectedCategory === cat ? "#1D4ED8" : "#2A2B30",
              border: "1px solid #2E2F34",
              color: selectedCategory === cat ? "#fff" : "#9CA3AF",
            }}
          >
            {CATEGORY_LABELS[cat]} ({groupedCategoryCounts[cat] || skills.filter((s) => s.category === cat).length})
          </button>
        ))}
      </div>

      {/* Skill list */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 24, color: "#9A9A9A" }}>Loading skills...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 24, color: "#6B7280", fontSize: 13 }}>
          No skills match your search.
        </div>
      ) : (
        filtered.map((skill) => (
          <SkillRow
            key={skill.name}
            skill={skill}
            executing={executing}
            results={results}
            onToggle={(name) => { }}
            onExecute={handleExecute}
          />
        ))
      )}

      <div style={{ marginTop: 12, fontSize: 11, color: "#4B5563", textAlign: "center" }}>
        {skills.length} skills &middot; {filtered.length} shown &middot; disabled via NEXA_SKILLS_ENABLED/DISABLED
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: "#2A2B30",
  border: "1px solid #2E2F34",
  color: "#ECECEC",
  padding: "6px 10px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 12,
};

const primaryBtnStyle: React.CSSProperties = {
  background: "#4A9EFF",
  border: "none",
  color: "#fff",
  padding: "8px 14px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  background: "#1A1B1E",
  border: "1px solid #2E2F34",
  color: "#ECECEC",
  padding: "8px 10px",
  borderRadius: 6,
  fontSize: 13,
  outline: "none",
};
