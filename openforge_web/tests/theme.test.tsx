/**
 * F-06 — Theme Toggle tests.
 * Verifies ThemeProvider persistence, system-mode resolution, and that the
 * toggle button cycles light → dark → system while applying --nexa-* tokens.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { cleanup, render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "../components/ThemeProvider";
import { ThemeToggle } from "../components/ThemeToggle";
import { THEME_STORAGE_KEY } from "../lib/theme";

// jsdom lacks matchMedia — provide a controllable stub.
let darkQueryMatches = true;
function stubMatchMedia() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: darkQueryMatches,
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

function ThemeStateProbe() {
  const { theme, resolvedTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
    </div>
  );
}

function renderApp() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
      <ThemeStateProbe />
    </ThemeProvider>
  );
}

describe("F-06 ThemeProvider + ThemeToggle", () => {
  beforeEach(() => {
    cleanup();
    window.localStorage.clear();
    darkQueryMatches = true;
    stubMatchMedia();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("style");
  });

  it("defaults to dark when nothing is stored", async () => {
    renderApp();
    expect(await screen.findByTestId("theme")).toHaveTextContent("dark");
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(
      document.documentElement.style.getPropertyValue("--nexa-bg")
    ).toBe("#0D0E10");
  });

  it("hydrates the persisted light theme from localStorage", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    renderApp();
    expect(await screen.findByTestId("theme")).toHaveTextContent("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(
      document.documentElement.style.getPropertyValue("--nexa-bg")
    ).toBe("#F4F5F7");
  });

  it("toggle cycles light → dark → system and persists each step", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    renderApp();
    const btn = screen.getByTestId("theme-toggle");
    expect(await screen.findByTestId("theme")).toHaveTextContent("light");

    await userEvent.click(btn); // light → dark
    expect(screen.getByTestId("theme")).toHaveTextContent("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await userEvent.click(btn); // dark → system
    expect(screen.getByTestId("theme")).toHaveTextContent("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");

    await userEvent.click(btn); // system → light
    expect(screen.getByTestId("theme")).toHaveTextContent("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(
      document.documentElement.style.getPropertyValue("--nexa-text")
    ).toBe("#1B1D21");
  });

  it("system mode resolves via prefers-color-scheme", async () => {
    darkQueryMatches = false; // OS is in light mode
    stubMatchMedia();
    window.localStorage.setItem(THEME_STORAGE_KEY, "system");
    renderApp();
    expect(await screen.findByTestId("resolved")).toHaveTextContent("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);

    // Flip the OS to dark and re-render with system still selected.
    darkQueryMatches = true;
    stubMatchMedia();
    await act(async () => {
      window.dispatchEvent(new Event("change"));
    });
  });

  it("system mode follows dark OS preference", async () => {
    darkQueryMatches = true;
    stubMatchMedia();
    window.localStorage.setItem(THEME_STORAGE_KEY, "system");
    renderApp();
    expect(await screen.findByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(
      document.documentElement.style.getPropertyValue("--nexa-accent")
    ).toBe("#4A9EFF");
  });

  it("globals.css reads the --nexa-* variables", async () => {
    // Spot-check that our stylesheet references the tokens (regression guard
    // against someone re-hardcoding the palette).
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const css = await fs.readFile(
      path.resolve(__dirname, "../app/globals.css"),
      "utf8"
    );
    expect(css).toContain("--nexa-bg");
    expect(css).toContain("var(--nexa-accent)");
    expect(css).toContain("html.light");
  });
});
