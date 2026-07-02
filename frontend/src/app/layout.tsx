/**
 * RetailFlow AI — Root Layout
 *
 * Provides:
 * - Inter font from next/font
 * - ThemeProvider (next-themes, default dark)
 * - QueryClientProvider (TanStack Query v5)
 * - Sonner toast container
 * - Axios client bootstrap (auth store wiring)
 * - Session hydration
 */
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "RetailFlow AI",
    template: "%s | RetailFlow AI",
  },
  description:
    "Intelligent queue management and analytics for retail operations. Real-time dashboards, AI-powered wait time predictions, and peak hours insights.",
  keywords: [
    "queue management",
    "retail analytics",
    "AI wait time prediction",
    "store operations",
  ],
  robots: { index: false, follow: false }, // internal tool — no indexing
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
