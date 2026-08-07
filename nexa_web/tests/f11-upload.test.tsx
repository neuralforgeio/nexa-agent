/**
 * F-11: Composer file upload (paperclip / drag-drop / image paste).
 *
 * Happy / edge / error coverage of the attachment flow in Composer.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { Composer } from "../components/Composer";

describe("Composer F-11 file upload", () => {
  const noop = () => {};
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    // JSDOM lacks these on the Attachment path.
    (global as any).URL.createObjectURL = vi.fn(() => "blob:preview");
    (global as any).URL.revokeObjectURL = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const jsonResponse = (body: unknown, status = 200) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      })
    );

  it("uploads a picked file and shows an attachment chip (happy path)", async () => {
    fetchSpy.mockReturnValue(jsonResponse({ ok: true, filename: "report.txt", path: "uploads/report.txt", size: 5 }));
    render(<Composer onSend={noop} onStop={noop} disabled={false} thinking={false} showSuggestions={false} />);

    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const file = new File(["hello"], "report.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByTestId("attachments")).toBeTruthy());
    expect(fetchSpy).toHaveBeenCalledWith("/api/upload", expect.objectContaining({ method: "POST" }));
    expect(screen.getByText("report.txt")).toBeTruthy();
  });

  it("appends the [Attached: ...] token to the outgoing message", async () => {
    const onSend = vi.fn();
    fetchSpy.mockReturnValue(jsonResponse({ ok: true, filename: "a.png", path: "uploads/a.png", size: 3 }));
    render(<Composer onSend={onSend} onStop={noop} disabled={false} thinking={false} showSuggestions={false} />);

    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [new File(["x"], "a.png", { type: "image/png" })] },
    });
    await waitFor(() => screen.getByTestId("attachments"));

    const ta = screen.getByPlaceholderText(/ask nexa anything/i);
    fireEvent.change(ta, { target: { value: "check this" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith(expect.stringContaining("check this"));
    expect(onSend).toHaveBeenCalledWith(expect.stringContaining("[Attached: uploads/a.png]"));
  });

  it("upload failure leaves the composer usable and adds no chip (error path)", async () => {
    fetchSpy.mockReturnValue(Promise.resolve(new Response("boom", { status: 500 })));
    render(<Composer onSend={noop} onStop={noop} disabled={false} thinking={false} showSuggestions={false} />);
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [new File(["x"], "bad.txt", { type: "text/plain" })] },
    });
    // No attachment should appear; body still usable.
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    expect(screen.queryByTestId("attachments")).toBeNull();
  });
});
