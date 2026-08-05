import { describe, it, expect, vi, beforeEach } from "vitest";
import { sendChatMessage } from "../lib/stream";

/**
 * F-01: Stop Generation — abort handling in the streaming layer.
 */
describe("sendChatMessage (F-01 abort)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("aborts before the first request: returns null, no fetch made", async () => {
    const ac = new AbortController();
    ac.abort(); // pre-aborted: user clicked Stop before starting
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const onStatus = vi.fn();

    const result = await sendChatMessage("hello", null, () => {}, onStatus, ac.signal);

    expect(result).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
    // "idle" because it never connected.
    expect(onStatus).toHaveBeenCalledWith("idle");
  });

  it("aborts mid-stream: passes AbortSignal to fetch, returns null", async () => {
    const ac = new AbortController();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input: unknown, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The user aborted a request.", "AbortError"));
          });
        })
    );
    const onEvent = vi.fn();

    const p = sendChatMessage("hello", null, onEvent, undefined, ac.signal);
    ac.abort();
    const result = await p;

    expect(result).toBeNull();
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/chat/stream",
      expect.objectContaining({ signal: ac.signal })
    );
    // No error event for user-initiated abort.
    expect(onEvent).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "error" })
    );
  });

  it("cleans status to idle on abort even after retries", async () => {
    const ac = new AbortController();
    let fetchCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input: unknown, init?: RequestInit) =>
        new Promise((_res, rej) => {
          fetchCalls++;
          init?.signal?.addEventListener("abort", () =>
            rej(new DOMException("aborted", "AbortError"))
          );
          // Reject as network error after short delay if not aborted yet.
          setTimeout(() => rej(new TypeError("Failed to fetch")), 50);
        })
    );
    const statuses: string[] = [];

    const p = sendChatMessage(
      "retry me",
      null,
      () => {},
      (s) => statuses.push(s),
      ac.signal
    );
    // Let the first attempt fail, then abort during reconnect delay.
    setTimeout(() => ac.abort(), 120);
    const result = await p;

    expect(result).toBeNull();
    expect(statuses.length).toBeGreaterThan(0);
    // Final status must be "idle" (no red banner after user abort).
    expect(statuses[statuses.length - 1]).toBe("idle");
  });
});
