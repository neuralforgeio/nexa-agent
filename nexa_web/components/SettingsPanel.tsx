/**
 * Nexa Agent — Settings Panel (v4.1.0)
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

import { useEffect, useState } from "react";
import { Settings, X, Plus, Trash2, Zap, CheckCircle2, XCircle, Loader2 } from "lucide-react";

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

export function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [activeName, setActiveName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<Record<string, "idle" | "testing" | "ok" | "fail">>({});

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
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(640px, 92vw)",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "#1A1B1E",
          border: "1px solid #2E2F34",
          borderRadius: 12,
          padding: 24,
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

        {error && (
          <div style={{ padding: "8px 12px", marginBottom: 12, background: "rgba(248,113,113,0.12)", borderRadius: 6, color: "#F87171", fontSize: 13 }}>
            {error}
          </div>
        )}

        {/* Provider list */}
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
          API keys are stored in ~/.nexa/secrets/providers.json (chmod 600).
          Terminal commands cannot access ~/.nexa/ (v3.0.0 security boundary).
        </div>
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
