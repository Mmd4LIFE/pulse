import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { Toaster } from "sonner";

import { AppGate } from "@/components/layout/app-gate";
import { AuthProvider } from "@/providers/auth-provider";
import { QueryProvider } from "@/providers/query-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Pulse",
  description: "A short-form social feed that lives inside Telegram.",
  applicationName: "Pulse",
  robots: { index: false, follow: false },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  // Telegram's webview keeps its own chrome; let the app paint edge to edge.
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1016" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        {/*
          The Telegram bridge must be in place before the app reads initData,
          so it loads ahead of hydration rather than lazily.
        */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <QueryProvider>
          <AuthProvider>
            <AppGate>{children}</AppGate>
            <Toaster
              position="top-center"
              toastOptions={{
                className:
                  "!bg-popover !text-popover-foreground !border-border !rounded-xl",
              }}
            />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
