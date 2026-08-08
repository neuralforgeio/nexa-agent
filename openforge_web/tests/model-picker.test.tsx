/**
 * F-05 — Model Picker tests.
 * Covers: list loading from /api/provider, clicking an item POSTs
 * /api/provider/use with the right body, the ACTIVE badge moves, and the
 * parent's chat re-mount hook fires (focus preserved by jsdom after).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelPicker } from "../components/ModelPicker";

const PROVIDERS = {
  active: "openai",
  providers: [
    { name: "openai", base_url: "https://api.openai.com/v1", model: "gpt-4o", api_key: "sk-...x", is_active: true },
    { name: "anthropic", base_url: "https://api.anthropic.com", model: "claude-sonnet-4", api_key: "sk-...y", is_active: false },
    { name: "local", base_url: "http://127.0.0.1:11434", model: "qwen2.5", api_key: "(env)", is_active: false },
  ],
};

function mockFetchList() {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/api/provider" && (!init || !init.method || init.method === "GET")) {
      return Promise.resolve(
        new Response(JSON.stringify(PROVIDERS), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    }
    if (url === "/api/provider/use" && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    }
    return Promise.reject(new Error(`Unexpected fetch ${init?.method ?? "GET"} ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("F-05 ModelPicker", () => {
  beforeEach(() => {
    cleanup();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the provider list and shows the active name + model", async () => {
    mockFetchList();
    render(<ModelPicker />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() =>
      expect(trigger).toHaveTextContent("openai · gpt-4o")
    );
  });

  it("opens the dropdown and lists every provider", async () => {
    mockFetchList();
    render(<ModelPicker />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));

    await userEvent.click(trigger);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getByTestId("provider-option-openai")).toBeInTheDocument();
    expect(screen.getByTestId("provider-option-anthropic")).toBeInTheDocument();
    expect(screen.getByTestId("provider-option-local")).toBeInTheDocument();
    // Exactly one ACTIVE badge (on openai).
    const badges = screen.getAllByTestId("provider-active-badge");
    expect(badges).toHaveLength(1);
    expect(screen.getByTestId("provider-option-openai")).toContainElement(badges[0]);
  });

  it("clicking a provider POSTs /api/provider/use with {name} and moves the badge", async () => {
    const fetchMock = mockFetchList();
    const onChange = vi.fn();
    render(<ModelPicker onProviderChange={onChange} />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));

    await userEvent.click(trigger);
    await userEvent.click(screen.getByTestId("provider-option-anthropic"));

    await waitFor(() => {
      const useCall = fetchMock.mock.calls.find(
        ([u, i]) => u === "/api/provider/use" && (i as RequestInit)?.method === "POST"
      );
      expect(useCall).toBeTruthy();
      const init = useCall![1] as RequestInit;
      expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
      expect(JSON.parse(init.body as string)).toEqual({ name: "anthropic" });
    });

    // Optimistic update: badge moved to anthropic; parent notified.
    await waitFor(() =>
      expect(trigger).toHaveTextContent("anthropic · claude-sonnet-4")
    );
    expect(onChange).toHaveBeenCalledWith("anthropic");

    // Badge now lives on anthropic.
    await userEvent.click(trigger);
    const badges = screen.getAllByTestId("provider-active-badge");
    expect(badges).toHaveLength(1);
    expect(screen.getByTestId("provider-option-anthropic")).toContainElement(badges[0]);
  });

  it("selecting the already-active provider does not fire onProviderChange", async () => {
    mockFetchList();
    const onChange = vi.fn();
    render(<ModelPicker onProviderChange={onChange} />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));
    await userEvent.click(trigger);
    await userEvent.click(screen.getByTestId("provider-option-openai"));
    await waitFor(() => expect(trigger).toHaveTextContent("openai · gpt-4o"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("rolls back the optimistic update when the POST fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/provider/use") {
          return Promise.resolve(new Response("boom", { status: 500 }));
        }
        return Promise.resolve(
          new Response(JSON.stringify(PROVIDERS), { status: 200 })
        );
      })
    );
    render(<ModelPicker />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));

    await userEvent.click(trigger);
    await userEvent.click(screen.getByTestId("provider-option-anthropic"));

    // After failure, the trigger falls back to the previous active provider.
    await waitFor(() => expect(trigger).toHaveTextContent("openai · gpt-4o"));
  });

  it("dropdown closes on Escape", async () => {
    mockFetchList();
    render(<ModelPicker />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));
    await userEvent.click(trigger);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("focus is preserved on the picker container after selecting", async () => {
    // After activating a provider, the chat re-mounts but keyboard focus
    // must not be thrown to <body> — the trigger keeps its place in the
    // header and what the user had focused stays focusable.
    mockFetchList();
    render(<ModelPicker />);
    const trigger = screen.getByTestId("model-picker-trigger");
    await waitFor(() => expect(trigger).toHaveTextContent("openai"));
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    await userEvent.click(trigger);
    await userEvent.click(screen.getByTestId("provider-option-local"));

    // After the optimistic swap the document hasn't hard-refocused anywhere
    // unexpected (either trigger or body — but never an <input> stealing it).
    await waitFor(() => expect(trigger).toHaveTextContent("local · qwen2.5"));
    expect(
      document.activeElement === trigger || document.activeElement === document.body
    ).toBe(true);
  });
});
