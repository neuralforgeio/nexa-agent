/**
 * F-02: Message Actions — copy / regenerate / edit-resubmit / branch.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MessageBubble } from "../components/MessageBubble";
import type { Message } from "../lib/theme";

const userMsg: Message = {
  id: "u-1", role: "user", content: "hello world", createdAt: new Date().toISOString(),
};
const asstMsg: Message = {
  id: "a-1", role: "assistant", content: "hi there", createdAt: new Date().toISOString(),
};

describe("MessageBubble F-02 actions", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("copy button writes message content to clipboard (happy path)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<MessageBubble message={userMsg} index={0} />);
    fireEvent.click(screen.getByRole("button", { name: /^copy$/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("hello world"));
    expect(await screen.findByText(/copied/i)).toBeTruthy();
  });

  it("regenerate button appears on assistant messages and calls onRegenerate with index", () => {
    const onRegenerate = vi.fn();
    render(<MessageBubble message={asstMsg} index={3} actions={{ onRegenerate }} />);
    fireEvent.click(screen.getByRole("button", { name: /regenerate/i }));
    expect(onRegenerate).toHaveBeenCalledWith(3);
  });

  it("regenerate hidden for assistant at index 0 (no preceding user prompt)", () => {
    const onRegenerate = vi.fn();
    render(<MessageBubble message={asstMsg} index={0} actions={{ onRegenerate }} />);
    expect(screen.queryByRole("button", { name: /regenerate/i })).toBeNull();
  });

  it("edit flow: opens textarea, submits via onEditSubmit only when text changed", async () => {
    const onEditSubmit = vi.fn();
    render(<MessageBubble message={userMsg} index={2} actions={{ onEditSubmit }} />);
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    const ta = screen.getByRole("textbox", { name: /edit-message/i }) as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "edited question" } });
    // The button's accessible name comes from its aria-label ("submit-edit"),
    // not the visible "Save & resubmit" text.
    fireEvent.click(screen.getByRole("button", { name: /submit-edit/i }));
    expect(onEditSubmit).toHaveBeenCalledWith(2, "edited question");
  });

  it("edit no-op when content unchanged (edge case)", () => {
    const onEditSubmit = vi.fn();
    render(<MessageBubble message={userMsg} index={2} actions={{ onEditSubmit }} />);
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit-edit/i }));
    expect(onEditSubmit).not.toHaveBeenCalled();
  });

  it("branch button calls onBranch with the message index", () => {
    const onBranch = vi.fn();
    render(<MessageBubble message={asstMsg} index={5} actions={{ onBranch }} />);
    fireEvent.click(screen.getByRole("button", { name: /branch/i }));
    expect(onBranch).toHaveBeenCalledWith(5);
  });

  it("error path: clipboard rejection does not crash or show Copied", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<MessageBubble message={userMsg} index={0} />);
    fireEvent.click(screen.getByRole("button", { name: /^copy$/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(screen.queryByText(/^copied$/i)).toBeNull();
  });
});
