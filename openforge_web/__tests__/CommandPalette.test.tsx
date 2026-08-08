/**
 * Unit tests — F-13 CommandPalette (components/CommandPalette.tsx)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette, type CommandItem } from "@/components/CommandPalette";

const COMMANDS: CommandItem[] = [
  { id: "new-chat", name: "New chat", description: "Start a fresh conversation.", hint: "Ctrl+N" },
  { id: "new-session", name: "New session", description: "Create a new session.", hint: "Ctrl+Shift+N" },
  { id: "open-settings", name: "Open settings", description: "Manage providers.", hint: "Ctrl+," },
  { id: "export-session", name: "Export session", description: "Download JSON.", hint: "Ctrl+E" },
  { id: "search-sessions", name: "Search sessions", description: "Find sessions.", hint: "Ctrl+F" },
  { id: "toggle-theme", name: "Toggle theme", description: "Flip theme.", hint: "Ctrl+Shift+L" },
  { id: "clear-chat", name: "Clear chat", description: "Remove messages.", hint: "Ctrl+Shift+X" },
  { id: "keyboard-shortcuts", name: "Keyboard shortcuts", description: "Show shortcuts.", hint: "Ctrl+/" },
];

describe("CommandPalette", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(<CommandPalette open={false} onClose={() => {}} commands={COMMANDS} />);
    expect(container.firstChild).toBeNull();
  });

  it("opens when `open` is true and lists all commands", () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    COMMANDS.forEach((c) => {
      expect(screen.getByText(c.name)).toBeInTheDocument();
    });
  });

  it("closes on Escape pressed in search input", async () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} commands={COMMANDS} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when clicking the dim overlay", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} commands={COMMANDS} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.mouseDown(dialog);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("filters commands by name when typing", async () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    const input = screen.getByLabelText(/command search/i);
    await userEvent.type(input, "theme");
    // Only "Toggle theme" remains.
    expect(screen.getByText("Toggle theme")).toBeInTheDocument();
    expect(screen.queryByText("New chat")).toBeNull();
  });

  it("filters by description substring", async () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    const input = screen.getByLabelText(/command search/i);
    await userEvent.type(input, "download");
    expect(screen.getByText("Export session")).toBeInTheDocument();
    expect(screen.queryByText("Open settings")).toBeNull();
  });

  it("shows empty-state when no commands match", async () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    const input = screen.getByLabelText(/command search/i);
    await userEvent.type(input, "should-not-match-anything-xyz");
    expect(screen.getByText(/no commands match/i)).toBeInTheDocument();
  });

  it("Enter triggers the active command action", async () => {
    const onExecute = vi.fn();
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} onExecute={onExecute} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onExecute).toHaveBeenCalledTimes(1);
    expect(onExecute.mock.calls[0][0].id).toBe("new-chat");
  });

  it("uses command-specific action when provided", async () => {
    const action = vi.fn();
    const cmds: CommandItem[] = [
      { id: "new-chat", name: "New chat", description: "Start fresh.", action },
    ];
    render(<CommandPalette open onClose={() => {}} commands={cmds} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("ArrowDown moves highlight then Enter selects that command", async () => {
    const onExecute = vi.fn();
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} onExecute={onExecute} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onExecute).toHaveBeenCalledTimes(1);
    expect(onExecute.mock.calls[0][0].id).toBe("open-settings");
  });

  it("ArrowUp clamps to index 0 and wraps nothing", async () => {
    const onExecute = vi.fn();
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} onExecute={onExecute} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "Enter" });
    // Still on the first command.
    expect(onExecute.mock.calls[0][0].id).toBe("new-chat");
  });

  it("highlight resets when the query changes", async () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    const input = screen.getByLabelText(/command search/i);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    await userEvent.type(input, "s");
    // First option should be selected again (aria-selected).
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");
  });

  it("renders keyboard hint column", () => {
    render(<CommandPalette open onClose={() => {}} commands={COMMANDS} />);
    expect(screen.getByText("Ctrl+N")).toBeInTheDocument();
    expect(screen.getByText("Ctrl+Shift+L")).toBeInTheDocument();
  });
});
