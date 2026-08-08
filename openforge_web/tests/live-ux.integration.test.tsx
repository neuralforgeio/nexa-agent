/**
 * Light integration test — mounts the real Page component with a stubbed
 * fetch and asserts that all four live-UX features wire together:
 *   F-05 model picker in the header
 *   F-06 theme toggle in the header
 *   F-07 keyboard-shortcuts overlay on "?"
 *   F-08 connection banner driven by /api/health polling
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Page from "../app/page";
import { ThemeProvider } from "../components/ThemeProvider";

const PROVIDERS = {
  active: "openai",
  providers: [
    { name: "openai", base_url: "https://api.openai.com/v1", model: "gpt-4o", api_key: "sk-...x", is_active: true },
    { name: "anthropic", base_url: "https://api.anthropic.com", model: "claude-sonnet-4", api_key: "sk-...y", is_active: false },
  ],
};

function setupFetch({ healthy = true }: { healthy?: boolean } = {}) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";

    if (url === "/api/health") {
      return healthy
        ? Promise.resolve(new Response(JSON.stringify({ version: "4.7.0" }), { status: 200 }))
        : Promise.reject(new Error("backend down"));
    }
    if (url === "/api/provider" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify(PROVIDERS), { status: 200 }));
    }
    if (url === "/api/provider/use" && method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    }
    if (url === "/api/sessions" && method === "GET") {
      return Promise.resolve(new Response(JSON.stringify({ sessions: [] }), { status: 200 }));
    }
    return Promise.resolve(
      new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } })
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubMatchMedia() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function renderPage() {
  return render(
    <ThemeProvider>
      <Page />
    </ThemeProvider>
  );
}

describe("integration — Page mounts F-05..F-08 together", () => {
  beforeEach(() => {
    cleanup();
    window.localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("style");
    document.body.style.overflow = "";
    stubMatchMedia();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("model picker + theme toggle appear in the header and shortcuts overlay opens on ?", async () => {
    setupFetch({ healthy: true });
    renderPage();

    // F-05: model picker trigger shows after provider list loads.
    const picker = await screen.findByTestId("model-picker-trigger");
    await waitFor(() => expect(picker).toHaveTextContent("openai · gpt-4o"));

    // F-06: theme toggle button visible.
    expect(screen.getByTestId("theme-toggle")).toBeInTheDocument();

    // F-07: press ? — shortcuts overlay renders and body locks.
    expect(screen.queryByRole("dialog", { name: /keyboard shortcuts/i })).toBeNull();
    act(() => {
      fireEvent.keyDown(window, { key: "?", shiftKey: true });
    });
    expect(await screen.findByRole("dialog", { name: /keyboard shortcuts/i })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");

    // Esc closes it and unlocks scroll.
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: /keyboard shortcuts/i })).toBeNull();
    expect(document.body.style.overflow).toBe("");
  });

  it("switching providers via the picker POSTs /api/provider/use and re-mounts chat", async () => {
    const fetchMock = setupFetch({ healthy: true });
    renderPage();

    const picker = await screen.findByTestId("model-picker-trigger");
    await waitFor(() => expect(picker).toHaveTextContent("openai · gpt-4o"));

    await userEvent.click(picker);
    await userEvent.click(await screen.findByTestId("provider-option-anthropic"));

    await waitFor(() => {
      const useCall = fetchMock.mock.calls.find(
        ([u, i]) => u === "/api/provider/use" && (i as RequestInit)?.method === "POST"
      );
      expect(useCall).toBeTruthy();
      expect(JSON.parse((useCall![1] as RequestInit).body as string)).toEqual({ name: "anthropic" });
    });
    await waitFor(() => expect(picker).toHaveTextContent("anthropic"));
  });

  it("F-08: no banner when backend is healthy, red banner when health probe fails", async () => {
    setupFetch({ healthy: true });
    const { unmount } = renderPage();
    // Let the health probe settle.
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/health", expect.anything()));
    expect(screen.queryByTestId("connection-banner")).toBeNull();
    unmount();

    cleanup();
    setupFetch({ healthy: false });
    renderPage();
    await waitFor(() => expect(screen.getByTestId("connection-banner")).toHaveAttribute("data-state", "down"));
  });
});
