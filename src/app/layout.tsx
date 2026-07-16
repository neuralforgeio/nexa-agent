import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/theme-provider";
import { NEXA_AUTHOR, NEXA_NAME, NEXA_TAGLINE, NEXA_VERSION } from "@/lib/nexa/constants";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: `${NEXA_NAME} v${NEXA_VERSION}`,
  description: `${NEXA_NAME} — ${NEXA_TAGLINE}. An advanced AI agent with file & terminal tools, persistent memory, and live web access.`,
  keywords: [
    "Nexa Agent",
    "AI agent",
    "Nexa",
    "Dearly Febriano Irwansyah",
    "tool calling",
    "AI assistant",
  ],
  authors: [{ name: NEXA_AUTHOR }],
  icons: {
    icon: "/nexa-agent.png",
    apple: "/nexa-agent.png",
  },
  openGraph: {
    title: `${NEXA_NAME} v${NEXA_VERSION}`,
    description: NEXA_TAGLINE,
    type: "website",
    images: ["/nexa-agent.png"],
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
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
