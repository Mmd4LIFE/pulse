import type { Metadata, Viewport } from "next";
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
      <head>
        {/*
          A plain blocking script, deliberately not next/script: with
          `beforeInteractive` Next queues the URL for its own loader to fetch
          during hydration, which can leave window.Telegram undefined when the
          app first mounts and reads initData. Loading it here guarantees the
          bridge exists before any of our code runs.
        */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="https://telegram.org/js/telegram-web-app.js" />
      </head>
      <body>
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
