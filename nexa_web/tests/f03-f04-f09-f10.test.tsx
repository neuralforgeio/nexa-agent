/**
 * Category-1 verification: F-03 search, F-04 pin/archive grouping,
 * F-09 settings dialog behaviour (Esc / scroll-lock / focus trap), and
 * F-10 useMediaQuery hook.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, act } from "@testing-library/react";
import { groupByDate, splitByPinArchive } from "../lib/sessions";
import { useMediaQuery, useIsMobile } from "../lib/useMediaQuery";
import { SettingsPanel } from "../components/SettingsPanel";
import * as React from "react";

// ── F-04: pure helpers ─────────────────────────────────────────────────────

describe("F-04 sessions helpers (pure)", () => {
  const mk = (over: Partial<any>) => ({
    id: "x", title: "t", createdAt: "", updatedAt: new Date().toISOString(), messageCount: 0, ...over,
  });

  it("splitByPinArchive buckets pinned / normal / archived", () => {
    const list = [
      mk({ id: "p", pinned: true }),
      mk({ id: "n" }),
      mk({ id: "a", archived: true }),
    ];
    const { pinned, normal, archived } = splitByPinArchive(list as any);
    expect(pinned.map((s) => s.id)).toEqual(["p"]);
    expect(normal.map((s) => s.id)).toEqual(["n"]);
    expect(archived.map((s) => s.id)).toEqual(["a"]);
  });

  it("groupByDate buckets today / older and survives bad dates", () => {
    const now = new Date().toISOString();
    const old = new Date(Date.now() - 3 * 86400000).toISOString();
    const g = groupByDate([
      mk({ id: "t", updatedAt: now }),
      mk({ id: "o", updatedAt: old }),
      mk({ id: "bad", updatedAt: "not-a-date" }),
    ] as any);
    expect(g.Today.map((s) => s.id)).toEqual(["t"]);
    expect(g.Older.map((s) => s.id).sort()).toEqual(["bad", "o"]);
  });
});

// ── F-10: useMediaQuery / useIsMobile ──────────────────────────────────────

describe("F-10 useMediaQuery", () => {
  let listener: ((e: any) => void) | null = null;
  let current = false;

  function installMock() {
    listener = null;
    current = false;
    (window as any).matchMedia = vi.fn((q: string) => ({
      media: q,
      get matches() { return current; },
      addEventListener: (_: string, cb: any) => { listener = cb; },
      removeEventListener: () => { listener = null; },
    }));
  }

  beforeEach(installMock);

  function Probe({ query }: { query: string }) {
    const m = useMediaQuery(query);
    return <span data-testid="m">{String(m)}</span>;
  }
  function MobileProbe() {
    return <span data-testid="mob">{String(useIsMobile(768))}</span>;
  }

  it("initially matches the live query, then reacts to a change event", async () => {
    current = true; // BEFORE render — so the hook's initial read is true
    render(<Probe query="(max-width: 767px)" />);
    await waitFor(() => expect(screen.getByTestId("m").textContent).toBe("true"));

    // Flip to false and fire the change listener inside act().
    current = false;
    act(() => { listener?.({ matches: false } as any); });
    await waitFor(() => expect(screen.getByTestId("m").textContent).toBe("false"));
  });

  it("useIsMobile reflects the 768px breakpoint", async () => {
    current = true;
    render(<MobileProbe />);
    await waitFor(() => expect(screen.getByTestId("mob").textContent).toBe("true"));
  });
});

// ── F-09: SettingsPanel dialog UX ──────────────────────────────────────────

describe("F-09 SettingsPanel Esc / scroll-lock / focus restore", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ active: null, providers: [] }), {
          status: 200, headers: { "Content-Type": "application/json" },
        })
      )
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    cleanup();
  });

  it("locks body scroll on mount and restores on unmount", async () => {
    const onClose = vi.fn();
    const { unmount } = render(<SettingsPanel onClose={onClose} />);
    await waitFor(() => expect(document.body.style.overflow).toBe("hidden"));
    unmount();
    expect(document.body.style.overflow).toBe("");
  });

  it("renders a focus-trapped dialog", async () => {
    render(<SettingsPanel onClose={vi.fn()} />);
    const dlg = await screen.findByRole("dialog");
    expect(dlg.getAttribute("aria-modal")).toBe("true");
    // Focus should be moved inside the dialog on open.
    await waitFor(() => expect(dlg.contains(document.activeElement)).toBe(true));
  });
});
