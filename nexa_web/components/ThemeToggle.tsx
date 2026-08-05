/**
 * Nexa Agent — Theme Toggle Button (F-06)
 *
 * Header icon button that cycles light → dark → system. Shows Sun/Moon/
 * Monitor icon from lucide-react. Uses the shared header-button styling so
 * it matches the sandbox/sidebar toggles in page.tsx.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import type { ThemeMode } from "../lib/theme";

const ORDER: ThemeMode[] = ["light", "dark", "system"];
const LABELS: Record<ThemeMode, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      title={`Theme: ${LABELS[theme]} (click for ${LABELS[next]})`}
      aria-label={`Theme: ${LABELS[theme]}. Switch to ${LABELS[next]}.`}
      data-testid="theme-toggle"
      style={{
        background: "none",
        border: "none",
        color: "var(--nexa-dim, #9A9A9A)",
        cursor: "pointer",
        padding: 4,
        borderRadius: 6,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {theme === "system" ? (
        <Monitor size={17} />
      ) : resolvedTheme === "dark" ? (
        <Moon size={17} />
      ) : (
        <Sun size={17} />
      )}
    </button>
  );
}
