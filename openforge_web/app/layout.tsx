/**
 * OpenForge — Root Layout (Hardened v2.1.0 → rebrand v4.16.0)
 *
 * Dark theme #141618. Uses system fonts (no next/font/google — avoids
 * network fetches at build time that fail in offline sandboxed environments).
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "../components/ThemeProvider";

export const metadata: Metadata = {
  title: "OpenForge — Forge intelligent code, locally.",
  description: "Local-first AI agent with tool-calling, memory, and streaming responses.",
  manifest: "/manifest.json",
  icons: { icon: "/icon_shape_open_forge.png", apple: "/icon_shape_open_forge.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        style={{
          margin: 0,
          padding: 0,
          // Background/color come from --forge-* tokens in globals.css so the
          // F-06 theme toggle recolors the whole app without a reload.
          background: "var(--forge-bg, #141618)",
          color: "var(--forge-text, #ECECEC)",
          fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
        }}
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
