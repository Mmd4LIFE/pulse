import type { Metadata, Viewport } from "next";
import { Inter, Vazirmatn } from "next/font/google";
import { Toaster } from "sonner";

import { AppGate } from "@/components/layout/app-gate";
import { AuthProvider } from "@/providers/auth-provider";
import { QueryProvider } from "@/providers/query-provider";

import "./globals.css";

/*
 * Two faces, one for each script the app is actually written in.
 *
 * X sets Latin text in Chirp, which is proprietary and cannot be shipped here.
 * Inter is the closest freely licensed grotesque -- same open apertures and
 * near-identical metrics -- so Latin reads the way it does there.
 *
 * The Persian half matters more. With no font declared at all, iOS had no
 * family in the stack with Arabic coverage and fell back to Geeza Pro, which
 * is why pulses looked heavy and cramped. Vazirmatn is the modern Persian UI
 * face, and sits much closer to the SF Arabic that X gets on iOS.
 *
 * Both are self-hosted by next/font, so there is no request to Google at
 * runtime and no third party in the critical path.
 */
const latin = Inter({
  subsets: ["latin"],
  variable: "--font-latin",
  display: "swap",
});

const arabic = Vazirmatn({
  subsets: ["arabic", "latin"],
  variable: "--font-arabic",
  display: "swap",
});

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
    <html
      lang="en"
      suppressHydrationWarning
      className={`${latin.variable} ${arabic.variable}`}
    >
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
