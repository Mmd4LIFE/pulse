"use client";

/** Wires Telegram's native back button to the router. */

import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { getWebApp } from "@/lib/telegram";

const ROOT_ROUTES = new Set(["/", "/explore", "/notifications", "/bookmarks"]);

export function useTelegramBackButton() {
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    const app = getWebApp();
    if (!app) return;

    // The tab bar is the way out of a root route, so no back button there.
    const isRoot = ROOT_ROUTES.has(pathname);
    const handler = () => router.back();

    if (isRoot) {
      app.BackButton.hide();
      return;
    }

    app.BackButton.onClick(handler);
    app.BackButton.show();

    return () => {
      app.BackButton.offClick(handler);
      app.BackButton.hide();
    };
  }, [pathname, router]);
}
