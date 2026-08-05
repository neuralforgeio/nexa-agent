/**
 * F-08 — Connection Status Banner tests.
 * Uses a stubbed fetch for /api/health and drives probes manually via the
 * hook's ``probe`` method so the tests stay deterministic.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { cleanup, render, screen, waitFor, act } from "@testing-library/react";
import {
  ConnectionStatusBanner,
  useConnectionHealth,
  type HealthState,
} from "../components/ConnectionStatusBanner";

interface Handle {
  state: HealthState;
  probe: () => Promise<void>;
}

function Harness({
  pollMs = 0,
  onHandle,
}: {
  pollMs?: number;
  onHandle?: (h: Handle) => void;
}) {
  const h = useConnectionHealth({ pollMs });
  if (onHandle) onHandle(h);
  return <ConnectionStatusBanner state={h.state} onRetry={h.probe} />;
}

/** Latest banner state attribute, or null when no banner is mounted. */
function bannerState(): string | null {
  return screen.queryByTestId("connection-banner")?.getAttribute("data-state") ?? null;
}

describe("F-08 ConnectionStatusBanner", () => {
  beforeEach(() => {
    cleanup();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("initial load: failed /api/health shows the red banner", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    render(<Harness />);
    await waitFor(() => expect(bannerState()).toBe("down"));
    const banner = screen.getByTestId("connection-banner");
    expect(banner.textContent).toMatch(/lost connection/i);
  });

  it("initial load: non-OK response also shows the red banner", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("err", { status: 500 }))
    );
    render(<Harness />);
    await waitFor(() => expect(bannerState()).toBe("down"));
  });

  it("initial load: healthy /api/health renders nothing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 200 }))
    );
    render(<Harness />);
    // Flush the automatic probe on mount.
    await waitFor(() => expect(screen.queryByTestId("connection-banner")).toBeNull());
    // Sanity: /api/health was actually called (so this isn't just "not yet probed").
    expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/health", expect.anything());
  });

  it("healthy → first failure is yellow reconnecting; second failure is red down", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 200 })) // mount probe ok
      .mockRejectedValue(new Error("blip")); // manual probes fail
    vi.stubGlobal("fetch", fetchMock);

    let latest!: Handle;
    render(<Harness onHandle={(h) => (latest = h)} />);
    await waitFor(() => expect(bannerState()).toBeNull());

    // First failure → yellow.
    await act(async () => {
      await latest.probe();
    });
    expect(bannerState()).toBe("reconnecting");
    expect(screen.getByTestId("connection-banner").textContent).toMatch(/reconnecting/i);

    // Second consecutive failure → red.
    await act(async () => {
      await latest.probe();
    });
    expect(bannerState()).toBe("down");
  });

  it("auto-dismisses on recovery", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("down")) // mount probe fails
      .mockResolvedValue(new Response("{}", { status: 200 })); // then healthy
    vi.stubGlobal("fetch", fetchMock);

    let latest!: Handle;
    render(<Harness onHandle={(h) => (latest = h)} />);
    await waitFor(() => expect(bannerState()).toBe("down"));

    // Next probe succeeds → banner auto-dismisses.
    await act(async () => {
      await latest.probe();
    });
    await waitFor(() => expect(bannerState()).toBeNull());
  });

  it("polling loop calls /api/health at the given interval", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<Harness pollMs={1000} />);
    // Flush the mount probe.
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    const initialCalls = fetchMock.mock.calls.length;
    expect(initialCalls).toBeGreaterThanOrEqual(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(initialCalls + 3);
    expect(bannerState()).toBeNull();
  });

  it("presentational banner: yellow for reconnecting, red for down, nothing for ok", () => {
    const { unmount } = render(<ConnectionStatusBanner state="reconnecting" />);
    expect(screen.getByTestId("connection-banner").style.background).toContain("warning");
    unmount();

    const { unmount: u2 } = render(<ConnectionStatusBanner state="down" />);
    expect(screen.getByTestId("connection-banner").style.background).toContain("error");
    u2();

    render(<ConnectionStatusBanner state="ok" />);
    expect(bannerState()).toBeNull();
  });
});
