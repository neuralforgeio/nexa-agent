/**
 * OpenForge — ThemeProvider (F-06)
 *
 * React context exposing ``{theme, setTheme, resolvedTheme}`` where theme is
 * "light" | "dark" | "system". Persists to localStorage key ``forge-theme``.
 * Applies the chosen token map to <html> as inline ``--forge-*`` custom
 * properties and toggles the ``light``/``dark`` class for CSS selectors.
 *
 * "system" follows ``prefers-color-scheme`` and live-updates on OS change.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  THEME_STORAGE_KEY,
  darkTokens,
  lightTokens,
  type ThemeMode,
  type ThemeTokens,
} from "../lib/theme";

export interface ThemeContextValue {
  theme: ThemeMode;
  resolvedTheme: "light" | "dark";
  setTheme: (t: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  resolvedTheme: "dark",
  setTheme: () => {},
});

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTokens(tokens: ThemeTokens, resolved: "light" | "dark"): void {
  const root = document.documentElement;
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(key, value);
  }
  root.classList.remove("light", "dark");
  root.classList.add(resolved);
  root.style.colorScheme = resolved;
}

// Apply the persisted (or default dark) theme synchronously before first
// paint on the client to avoid a white flash.
const PRE_PAINT = `(function(){try{var t=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY
)})||"dark";var d=t==="system"?window.matchMedia("(prefers-color-scheme: dark)").matches:t!=="light";document.documentElement.classList.add(d?"dark":"light");document.documentElement.style.colorScheme=d?"dark":"light";}catch(e){document.documentElement.classList.add("dark");}})();`;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>("dark");

  // Hydrate from localStorage once mounted.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (raw === "light" || raw === "dark" || raw === "system") setThemeState(raw);
    } catch {
      /* storage unavailable (private mode) */
    }
  }, []);

  const resolvedTheme: "light" | "dark" =
    theme === "system" ? (systemPrefersDark() ? "dark" : "light") : theme;

  // Apply tokens + classes whenever the *resolved* theme changes.
  useEffect(() => {
    applyTokens(resolvedTheme === "dark" ? darkTokens : lightTokens, resolvedTheme);
  }, [resolvedTheme]);

  // When in "system" mode, follow OS-level preference changes live.
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setThemeState((t) => t); // re-render to re-resolve
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    return undefined;
  }, [theme]);

  const setTheme = useCallback((t: ThemeMode) => {
    setThemeState(t);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme]
  );

  return (
    <ThemeContext.Provider value={value}>
      {/* Pre-paint script: set the class before React hydrates. */}
      <script dangerouslySetInnerHTML={{ __html: PRE_PAINT }} />
      {children}
    </ThemeContext.Provider>
  );
}
