/**
 * Nexa Agent — Root Layout
 *
 * Dark theme #141618, Inter + JetBrains Mono fonts.
 * Nexa logo as favicon.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const jetbrainsMono = JetBrains_Mono({ variable: "--font-jetbrains-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nexa Agent — Advanced AI Agent",
  description: "Local AI agent with tool-calling, memory, and streaming responses.",
  icons: { icon: "/nexa-agent.png", apple: "/nexa-agent.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable}`} style={{
        margin: 0, padding: 0, background: "#141618", color: "#ECECEC",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        WebkitFontSmoothing: "antialiased",
      }}>
        {children}
      </body>
    </html>
  );
}
