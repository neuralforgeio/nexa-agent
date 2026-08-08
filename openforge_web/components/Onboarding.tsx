/**
 * Nexa Agent — F-14 Onboarding Wizard (first-run)
 *
 * Multi-step modal shown the first time a user opens the app:
 *   1. Welcome — brand + what Nexa is.
 *   2. Add provider — name select, model, API key, "Test connection"
 *      hitting `/api/provider/test`.
 *   3. Try sample prompt — inserts a sample prompt into the Composer
 *      and submits it (via `onRunSample` callback so the page can wire
 *      its own send handler / mock for tests).
 *   4. Complete — marks `hasCompletedOnboarding` in localStorage and
 *      closes.
 *
 * Skippable ("Skip for now") and resumable (parent can re-open it by
 * forcing `open={true}` from settings).
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Sparkles, X, XCircle, Zap } from "lucide-react";

export const LS_ONBOARDING = "nexa-onboarding-complete";
export const SAMPLE_PROMPT =
  "Say hello to Nexa: introduce yourself and list three things you can help me build today.";

export type ProviderKind = "openai" | "ollama" | "tokenrouter" | "llamacpp";

const PROVIDER_PRESETS: Record<ProviderKind, { label: string; defaultModel: string; baseUrl: string }> = {
  openai:      { label: "OpenAI",            defaultModel: "gpt-4o-mini",       baseUrl: "https://api.openai.com/v1" },
  ollama:      { label: "Ollama (local)",    defaultModel: "llama3.1",          baseUrl: "http://127.0.0.1:11434/v1" },
  tokenrouter: { label: "TokenRouter",       defaultModel: "auto:balance",      baseUrl: "https://api.tokenrouter.io/v1" },
  llamacpp:    { label: "llama.cpp (local)", defaultModel: "local-model",       baseUrl: "http://127.0.0.1:8080/v1" },
};

export interface OnboardingProps {
  /** Controlled open. When undefined, auto-opens on first run. */
  open?: boolean;
  onClose?: () => void;
  /** Called when the user clicks "Try a sample prompt" on step 3. The
      parent should insert `SAMPLE_PROMPT` into the Composer and submit
      it (or mock it in tests). */
  onRunSample?: (prompt: string) => void;
}

type Step = 0 | 1 | 2 | 3;
type TestStatus = "idle" | "testing" | "ok" | "fail";

export function Onboarding({ open: openProp, onClose, onRunSample }: OnboardingProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [step, setStep] = useState<Step>(0);

  // Step-2 form state.
  const [provider, setProvider] = useState<ProviderKind>("openai");
  const [model, setModel] = useState(PROVIDER_PRESETS.openai.defaultModel);
  const [apiKey, setApiKey] = useState("");
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testError, setTestError] = useState<string | null>(null);

  const open = openProp !== undefined ? openProp : internalOpen;

  // First-run auto-open.
  useEffect(() => {
    if (openProp !== undefined) return;
    try {
      if (typeof window !== "undefined" && window.localStorage.getItem(LS_ONBOARDING) !== "1") {
        setInternalOpen(true);
      }
    } catch {
      /* ignore storage errors */
    }
  }, [openProp]);

  useEffect(() => {
    // Keep form defaults in sync with the selected provider preset.
    setModel(PROVIDER_PRESETS[provider].defaultModel);
  }, [provider]);

  const close = useCallback(() => {
    setStep(0);
    if (onClose) onClose();
    else setInternalOpen(false);
  }, [onClose]);

  const complete = useCallback(() => {
    try {
      window.localStorage.setItem(LS_ONBOARDING, "1");
    } catch {
      /* ignore storage errors */
    }
    close();
  }, [close]);

  const handleTestConnection = useCallback(async () => {
    setTestStatus("testing");
    setTestError(null);
    try {
      const res = await fetch("/api/provider/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: provider,
          base_url: PROVIDER_PRESETS[provider].baseUrl,
          api_key: apiKey,
          model,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        setTestStatus("ok");
      } else {
        setTestStatus("fail");
        setTestError(data.error || `HTTP ${res.status}`);
      }
    } catch (err) {
      setTestStatus("fail");
      setTestError(err instanceof Error ? err.message : "Connection failed");
    }
  }, [provider, apiKey, model]);

  const handleRunSample = useCallback(() => {
    onRunSample?.(SAMPLE_PROMPT);
  }, [onRunSample]);

  const totalSteps = 4;
  const next = useCallback(() => setStep((s) => (s < 3 ? ((s + 1) as Step) : s)), []);
  const back = useCallback(() => setStep((s) => (s > 0 ? ((s - 1) as Step) : s)), []);

  const footer = useMemo(
    () => (
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 20,
          gap: 8,
        }}
      >
        <button
          onClick={complete}
          data-testid="onboarding-skip"
          style={{
            background: "none",
            border: "none",
            color: "#9A9A9A",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Skip for now
        </button>
        <div style={{ display: "flex", gap: 8 }}>
          {step > 0 && (
            <button
              onClick={back}
              data-testid="onboarding-back"
              style={{
                padding: "8px 14px",
                background: "#2A2B30",
                border: "1px solid #2E2F34",
                color: "#ECECEC",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Back
            </button>
          )}
          {step < 3 ? (
            <button
              onClick={next}
              data-testid="onboarding-next"
              style={{
                padding: "8px 14px",
                background: "#4A9EFF",
                border: "none",
                color: "#fff",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              Next
            </button>
          ) : (
            <button
              onClick={complete}
              data-testid="onboarding-finish"
              style={{
                padding: "8px 14px",
                background: "#4A9EFF",
                border: "none",
                color: "#fff",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              Finish
            </button>
          )}
        </div>
      </div>
    ),
    [step, back, next, complete],
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Onboarding wizard"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 210,
        background: "rgba(0,0,0,0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          width: "min(560px, 92vw)",
          background: "#1A1B1E",
          border: "1px solid #2E2F34",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 12px 40px rgba(0,0,0,0.4)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Sparkles size={18} color="#4A9EFF" />
            <h2
              style={{
                margin: 0,
                fontSize: 18,
                fontWeight: 600,
                color: "#ECECEC",
              }}
            >
              Welcome to Nexa
            </h2>
          </div>
          <button
            onClick={close}
            aria-label="Close onboarding"
            style={{
              background: "transparent",
              border: "none",
              color: "#9A9A9A",
              cursor: "pointer",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: 18,
          }}
          aria-label={`Step ${step + 1} of ${totalSteps}`}
        >
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              aria-hidden="true"
              style={{
                height: 3,
                flex: 1,
                borderRadius: 2,
                background: i <= step ? "#4A9EFF" : "#2E2F34",
                transition: "background 0.2s",
              }}
            />
          ))}
        </div>

        {/* Step body */}
        {step === 0 && (
          <div data-testid="onboarding-step-welcome">
            <h3 style={{ margin: "4px 0 10px", fontSize: 16, color: "#ECECEC" }}>
              Private AI, on your machine.
            </h3>
            <p style={{ margin: 0, fontSize: 13, color: "#9A9A9A", lineHeight: 1.6 }}>
              Nexa Agent is a local, open-source AI workbench. It chats, edits,
              runs commands in a sandboxed terminal, and keeps your sessions
              on disk — no third-party cloud required.
            </p>
            <p style={{ margin: "12px 0 0", fontSize: 13, color: "#9A9A9A", lineHeight: 1.6 }}>
              This wizard will help you hook up a model provider and run your
              first prompt in under a minute.
            </p>
          </div>
        )}

        {step === 1 && (
          <div data-testid="onboarding-step-provider">
            <h3 style={{ margin: "4px 0 10px", fontSize: 16, color: "#ECECEC" }}>
              Add a provider
            </h3>
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "#9A9A9A" }}>
              Pick a provider below. Paste an API key if required; local
              providers like Ollama can leave it blank.
            </p>
            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 12, color: "#9A9A9A" }}>
                Provider
                <select
                  aria-label="Provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as ProviderKind)}
                  style={{
                    width: "100%",
                    marginTop: 4,
                    padding: "8px 10px",
                    background: "#141618",
                    color: "#ECECEC",
                    border: "1px solid #2E2F34",
                    borderRadius: 6,
                    fontSize: 13,
                  }}
                >
                  {(Object.keys(PROVIDER_PRESETS) as ProviderKind[]).map((k) => (
                    <option key={k} value={k}>
                      {PROVIDER_PRESETS[k].label}
                    </option>
                  ))}
                </select>
              </label>

              <label style={{ fontSize: 12, color: "#9A9A9A" }}>
                Model
                <input
                  aria-label="Model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={PROVIDER_PRESETS[provider].defaultModel}
                  style={{
                    width: "100%",
                    marginTop: 4,
                    padding: "8px 10px",
                    background: "#141618",
                    color: "#ECECEC",
                    border: "1px solid #2E2F34",
                    borderRadius: 6,
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </label>

              <label style={{ fontSize: 12, color: "#9A9A9A" }}>
                API key (optional for local)
                <input
                  aria-label="API key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-…"
                  style={{
                    width: "100%",
                    marginTop: 4,
                    padding: "8px 10px",
                    background: "#141618",
                    color: "#ECECEC",
                    border: "1px solid #2E2F34",
                    borderRadius: 6,
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </label>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button
                  onClick={handleTestConnection}
                  disabled={testStatus === "testing"}
                  data-testid="onboarding-test-connection"
                  style={{
                    padding: "8px 12px",
                    background: "#2A2B30",
                    border: "1px solid #2E2F34",
                    color: "#ECECEC",
                    borderRadius: 6,
                    cursor: testStatus === "testing" ? "not-allowed" : "pointer",
                    fontSize: 13,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    opacity: testStatus === "testing" ? 0.6 : 1,
                  }}
                >
                  {testStatus === "testing" ? (
                    <>
                      <Loader2 size={13} className="animate-spin" /> Testing…
                    </>
                  ) : (
                    <>
                      <Zap size={13} /> Test connection
                    </>
                  )}
                </button>
                {testStatus === "ok" && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, color: "#4ADE80" }}>
                    <CheckCircle2 size={13} /> Connected
                  </span>
                )}
                {testStatus === "fail" && (
                  <span
                    data-testid="onboarding-test-fail"
                    style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, color: "#F87171" }}
                  >
                    <XCircle size={13} /> {testError ?? "Failed"}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div data-testid="onboarding-step-sample">
            <h3 style={{ margin: "4px 0 10px", fontSize: 16, color: "#ECECEC" }}>
              Try your first prompt
            </h3>
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "#9A9A9A", lineHeight: 1.6 }}>
              We&apos;ll drop a sample prompt into your composer and send it,
              so you can watch Nexa stream a reply in real time.
            </p>
            <div
              style={{
                padding: 12,
                background: "#141618",
                border: "1px solid #2E2F34",
                borderRadius: 8,
                fontSize: 13,
                color: "#CFCFCF",
                marginBottom: 12,
                fontStyle: "italic",
              }}
            >
              “{SAMPLE_PROMPT}”
            </div>
            <button
              onClick={handleRunSample}
              data-testid="onboarding-run-sample"
              style={{
                padding: "8px 14px",
                background: "#4A9EFF",
                border: "none",
                color: "#fff",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              Run sample prompt
            </button>
          </div>
        )}

        {step === 3 && (
          <div data-testid="onboarding-step-complete">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <CheckCircle2 size={20} color="#4ADE80" />
              <h3 style={{ margin: 0, fontSize: 16, color: "#ECECEC" }}>You&apos;re all set!</h3>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "#9A9A9A", lineHeight: 1.6 }}>
              Nexa is ready. Press <kbd style={{ fontFamily: "inherit", background: "#0F1012", padding: "1px 4px", borderRadius: 3, border: "1px solid #2E2F34" }}>Ctrl+K</kbd> any time
              to open the command palette, or <kbd style={{ fontFamily: "inherit", background: "#0F1012", padding: "1px 4px", borderRadius: 3, border: "1px solid #2E2F34" }}>Ctrl+B</kbd> to toggle the sidebar.
              You can reopen this wizard later from Settings.
            </p>
          </div>
        )}

        {footer}
      </div>
    </div>
  );
}
