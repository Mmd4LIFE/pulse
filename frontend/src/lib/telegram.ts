/**
 * A safe façade over the Telegram WebApp bridge.
 *
 * Every call has to work in three settings: inside Telegram, in a plain browser
 * during development, and during server rendering where `window` is undefined.
 * Guarding here keeps that branching out of the components.
 */

import type { TelegramWebApp } from "@/types/telegram";

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

export function isInsideTelegram(): boolean {
  const app = getWebApp();
  return Boolean(app?.initData);
}

/**
 * Resolve once the Telegram bridge has attached itself to `window`.
 *
 * The script is loaded synchronously in the document head, so in practice this
 * returns immediately. It exists so that a slow or blocked bridge degrades into
 * a short wait rather than a misdetected "not in Telegram", which in production
 * means being bounced to a disabled dev login.
 */
export function waitForWebApp(timeoutMs = 3000): Promise<TelegramWebApp | null> {
  if (typeof window === "undefined") return Promise.resolve(null);

  const existing = getWebApp();
  if (existing) return Promise.resolve(existing);

  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      const app = getWebApp();
      if (app) return resolve(app);
      if (Date.now() - started >= timeoutMs) return resolve(null);
      window.setTimeout(tick, 50);
    };
    tick();
  });
}

/** Prepare the webview: full height, no accidental swipe-to-close. */
export function initialiseWebApp(): void {
  const app = getWebApp();
  if (!app) return;

  app.ready();
  app.expand();

  // Only available from Bot API 7.7; older clients simply do not have it.
  try {
    app.disableVerticalSwipes?.();
  } catch {
    /* older client */
  }
}

type HapticStyle = "light" | "medium" | "heavy" | "rigid" | "soft";

export const haptics = {
  tap(style: HapticStyle = "light"): void {
    try {
      getWebApp()?.HapticFeedback.impactOccurred(style);
    } catch {
      /* unsupported client */
    }
  },
  select(): void {
    try {
      getWebApp()?.HapticFeedback.selectionChanged();
    } catch {
      /* unsupported client */
    }
  },
  notify(type: "error" | "success" | "warning"): void {
    try {
      getWebApp()?.HapticFeedback.notificationOccurred(type);
    } catch {
      /* unsupported client */
    }
  },
};

/** Confirm through Telegram's native dialog, falling back to the browser's. */
export function confirmAction(message: string): Promise<boolean> {
  const app = getWebApp();
  if (!app) return Promise.resolve(window.confirm(message));
  return new Promise((resolve) => {
    try {
      app.showConfirm(message, (ok) => resolve(Boolean(ok)));
    } catch {
      resolve(window.confirm(message));
    }
  });
}

export function openExternal(url: string): void {
  const app = getWebApp();
  if (app) {
    if (url.startsWith("https://t.me/") || url.startsWith("tg://")) {
      app.openTelegramLink(url);
    } else {
      app.openLink(url);
    }
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

/**
 * Map Telegram's theme onto the CSS custom properties the UI is built from,
 * so the app takes on the colours of whatever client it is opened in.
 */
export function applyTelegramTheme(): "light" | "dark" {
  const app = getWebApp();
  const root = document.documentElement;

  // The Telegram script loads in an ordinary browser too, where it reports a
  // hardcoded "light" scheme. Only believe it when there is signed initData,
  // which is the one signal that we really are inside a Telegram client.
  const scheme = isInsideTelegram() ? app!.colorScheme : preferredScheme();
  root.classList.toggle("dark", scheme === "dark");

  const params = isInsideTelegram() ? app?.themeParams : undefined;
  if (params) {
    const set = (name: string, value?: string) => {
      if (value) root.style.setProperty(name, value);
    };
    set("--tg-bg", params.bg_color);
    set("--tg-text", params.text_color);
    set("--tg-hint", params.hint_color);
    set("--tg-link", params.link_color);
    set("--tg-button", params.button_color);
    set("--tg-button-text", params.button_text_color);
    set("--tg-secondary-bg", params.secondary_bg_color);
  }

  // Match the Telegram header to the app background so the seam disappears.
  if (isInsideTelegram()) {
    try {
      app?.setHeaderColor(scheme === "dark" ? "#0b1016" : "#ffffff");
      app?.setBackgroundColor(scheme === "dark" ? "#0b1016" : "#ffffff");
    } catch {
      /* older client */
    }
  }

  return scheme;
}

function preferredScheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Publish the usable viewport height as a CSS variable for full-height layouts. */
export function trackViewport(): () => void {
  const app = getWebApp();
  const apply = () => {
    const height = app?.viewportStableHeight || window.innerHeight;
    document.documentElement.style.setProperty("--tg-viewport", `${height}px`);
    const inset = app?.contentSafeAreaInset ?? app?.safeAreaInset;
    document.documentElement.style.setProperty("--tg-safe-top", `${inset?.top ?? 0}px`);
    document.documentElement.style.setProperty(
      "--tg-safe-bottom",
      `${inset?.bottom ?? 0}px`,
    );
  };

  apply();
  app?.onEvent("viewportChanged", apply);
  window.addEventListener("resize", apply);

  return () => {
    app?.offEvent("viewportChanged", apply);
    window.removeEventListener("resize", apply);
  };
}
