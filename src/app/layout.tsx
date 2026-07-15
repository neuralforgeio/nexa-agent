import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { NEXA_AUTHOR, NEXA_NAME, NEXA_TAGLINE, NEXA_VERSION } from "@/lib/nexa/constants";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: `${NEXA_NAME} v${NEXA_VERSION}`,
  description: `${NEXA_NAME} — ${NEXA_TAGLINE}. An advanced AI agent with a tool-calling core, persistent memory and a terminal-grade interface.`,
  keywords: [
    "Nexa Agent",
    "AI agent",
    "Nexa",
    "Dearly Febriano Irwansyah",
    "tool calling",
    "AI assistant",
  ],
  authors: [{ name: NEXA_AUTHOR }],
  openGraph: {
    title: `${NEXA_NAME} v${NEXA_VERSION}`,
    description: NEXA_TAGLINE,
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-mono antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
