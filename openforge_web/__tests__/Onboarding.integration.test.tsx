/**
 * Integration tests — F-14 Onboarding with mocked `/api/provider/test`
 *
 * Verifies that the "Test connection" button actually POSTs to the
 * provider test endpoint with the right payload, and that success /
 * failure UI states render correctly.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Onboarding } from "@/components/Onboarding";

type FetchArgs = [RequestInfo | URL, RequestInit?];

describe("Onboarding — /api/provider/test integration", () => {
  const realFetch = globalThis.fetch;

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
    vi.restoreAllMocks();
  });

  it("calls POST /api/provider/test with provider payload", async () => {
    const fetchMock = vi.fn((_url: FetchArgs[0], _init?: FetchArgs[1]) =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    // Fill model + key.
    await userEvent.clear(screen.getByLabelText(/^model$/i));
    await userEvent.type(screen.getByLabelText(/^model$/i), "gpt-4o-mini");
    await userEvent.type(screen.getByLabelText(/api key/i), "sk-test-123");

    await userEvent.click(screen.getByTestId("onboarding-test-connection"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as FetchArgs;
    expect(String(url)).toBe("/api/provider/test");
    expect(init?.method).toBe("POST");
    const body = JSON.parse(String(init?.body ?? "{}")) as {
      name: string;
      base_url: string;
      api_key: string;
      model: string;
    };
    expect(body.name).toBe("openai");
    expect(body.base_url).toBe("https://api.openai.com/v1");
    expect(body.api_key).toBe("sk-test-123");
    expect(body.model).toBe("gpt-4o-mini");

    // Success indicator rendered.
    await screen.findByText(/connected/i);
  });

  it("renders failure state when API returns ok:false", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: false, error: "invalid key" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )) as unknown as typeof fetch;

    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-test-connection"));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-test-fail")).toHaveTextContent(/invalid key/i);
    });
  });

  it("renders failure state on network error", async () => {
    globalThis.fetch = (() =>
      Promise.reject(new Error("ECONNREFUSED"))) as unknown as typeof fetch;

    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-test-connection"));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-test-fail")).toHaveTextContent(/ECONNREFUSED/i);
    });
  });

  it("uses the selected provider's base URL when switched to ollama", async () => {
    const fetchMock = vi.fn((_u: FetchArgs[0], _i?: FetchArgs[1]) =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.selectOptions(screen.getByLabelText(/provider/i), "ollama");
    await userEvent.click(screen.getByTestId("onboarding-test-connection"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as FetchArgs;
    const body = JSON.parse(String(init?.body ?? "{}")) as { name: string; base_url: string };
    expect(body.name).toBe("ollama");
    expect(body.base_url).toBe("http://127.0.0.1:11434/v1");
  });
});
