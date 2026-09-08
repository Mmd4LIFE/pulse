import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle so the runtime image can skip
  // node_modules entirely.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  images: {
    // Avatars come from Telegram's CDN; uploads are served from our own origin.
    remotePatterns: [
      { protocol: "https", hostname: "t.me" },
      { protocol: "https", hostname: "**.telegram.org" },
      { protocol: "https", hostname: "**.telesco.pe" },
    ],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Telegram renders the Mini App inside its own webview frame.
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors https://web.telegram.org https://telegram.org self;",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
