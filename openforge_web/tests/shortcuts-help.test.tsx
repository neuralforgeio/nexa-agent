/**
 * F-07 — Keyboard Shortcuts overlay tests.
 * The hook listens for "?", the component closes on Esc / outside click,
 * and body scroll locks while open.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { cleanup, render, screen, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShortcutsHelp, useShortcutsHelp, SHORTCUTS } from "../components/ShortcutsHelp";

function Harness() {
  const { open, setOpen } = useShortcutsHelp();
  return (
    <div>
      <span data-testid="open-state">{open ? "open" : "closed"}</span>
      {open && <ShortcutsHelp onClose={() => setOpen(false)} />}
    </div>
  );
}

function pressQuestionMark() {
  fireEvent.keyDown(window, { key: "?", shiftKey: true });
}

describe("F-07 ShortcutsHelp", () => {
  beforeEach(() => {
    cleanup();
    document.body.style.overflow = "";
  });

  it("opens when ? is pressed", async () => {
    render(<Harness />);
    expect(screen.getByTestId("open-state")).toHaveTextContent("closed");
    act(() => pressQuestionMark());
    expect(screen.getByTestId("open-state")).toHaveTextContent("open");
    expect(screen.getByRole("dialog", { name: /keyboard shortcuts/i })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    render(<Harness />);
    act(() => pressQuestionMark());
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("open-state")).toHaveTextContent("closed");
  });

  it("closes when clicking the backdrop (outside the dialog)", async () => {
    render(<Harness />);
    act(() => pressQuestionMark());
    const overlay = screen.getByTestId("shortcuts-overlay");
    // Clicking the overlay itself (target === currentTarget) closes.
    fireEvent.mouseDown(overlay);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does NOT close when clicking inside the dialog content", async () => {
    render(<Harness />);
    act(() => pressQuestionMark());
    const dialog = screen.getByRole("dialog");
    fireEvent.mouseDown(dialog.firstChild as Element);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders 8-10 shortcut rows with keybinding + description", async () => {
    render(<Harness />);
    act(() => pressQuestionMark());
    // At least 8 rows, at most 10 per the spec.
    expect(SHORTCUTS.length).toBeGreaterThanOrEqual(8);
    expect(SHORTCUTS.length).toBeLessThanOrEqual(10);
    // Spot-check a few descriptions are present.
    expect(screen.getByText("New chat")).toBeInTheDocument();
    expect(screen.getByText("Toggle sidebar")).toBeInTheDocument();
    expect(screen.getByText("Focus composer")).toBeInTheDocument();
    expect(screen.getByText("Scroll to top")).toBeInTheDocument();
    expect(screen.getByText("Show this help")).toBeInTheDocument();
  });

  it("locks body scroll while open, restores on close", async () => {
    render(<Harness />);
    expect(document.body.style.overflow).toBe("");
    act(() => pressQuestionMark());
    expect(document.body.style.overflow).toBe("hidden");
    await userEvent.keyboard("{Escape}");
    expect(document.body.style.overflow).toBe("");
  });

  it("does not open when ? is typed inside an input", async () => {
    render(
      <div>
        <input data-testid="free-input" />
        <Harness />
      </div>
    );
    const input = screen.getByTestId("free-input");
    input.focus();
    fireEvent.keyDown(input, { key: "?", shiftKey: true });
    expect(screen.getByTestId("open-state")).toHaveTextContent("closed");
  });

  it("toggles closed if ? is pressed again", async () => {
    render(<Harness />);
    act(() => pressQuestionMark());
    expect(screen.getByTestId("open-state")).toHaveTextContent("open");
    act(() => pressQuestionMark());
    expect(screen.getByTestId("open-state")).toHaveTextContent("closed");
  });
});
