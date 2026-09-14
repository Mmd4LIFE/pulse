/**
 * A safe façade over the Telegram WebApp bridge.
 *
 * Every call has to work in three settings: inside Telegram, in a plain browser
 * during development, and during server rendering where `window` is undefined.
 * Guarding here keeps that branching out of the components.
 */

import type { TelegramWebApp } from "@/types/telegram";

/** Matches --background in globals.css, which the client cannot read. */
const APP_BACKGROUND = "#f2f4f8";

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
export function waitForWebApp(
  timeoutMs = 3000,
): Promise<TelegramWebApp | null> {
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
 * Whether this client can open the native chat picker for a prepared message.
 *
 * ``shareMessage`` arrived in Bot API 8.0. Older clients still have the app's
 * own object, so the method has to be looked for rather than assumed, and the
 * version asked as well: some clients define the name and then reject the call.
 */
export function canShareMessage(): boolean {
  const app = getWebApp();
  if (!app || typeof app.shareMessage !== "function") return false;
  try {
    return app.isVersionAtLeast("8.0");
  } catch {
    return false;
  }
}

/**
 * Hand a prepared message to Telegram and let the user choose a chat.
 *
 * Resolves to whether it was actually sent: closing the picker is a normal
 * outcome, not a failure, and should leave no error behind.
 */
export function shareMessage(preparedMessageId: string): Promise<boolean> {
  const app = getWebApp();
  if (!app?.shareMessage) return Promise.reject(new Error("unsupported"));

  return new Promise((resolve, reject) => {
    try {
      app.shareMessage!(preparedMessageId, (sent) => resolve(Boolean(sent)));
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Tell the Telegram client what the app looks like.
 *
 * Pulse has one theme, so there is nothing to detect and nothing to follow.
 * The client still needs to be told, or its own header and background stay in
 * whatever theme the user has set and the app appears to float in a strip of
 * someone else's colour.
 */
export function applyTelegramTheme(): void {
  const app = getWebApp();
  if (!app) return;

  try {
    app.setHeaderColor(APP_BACKGROUND);
    app.setBackgroundColor(APP_BACKGROUND);
  } catch {
    /* older client */
  }
}

/** Publish the usable viewport height as a CSS variable for full-height layouts. */
export function trackViewport(): () => void {
  const app = getWebApp();
  const apply = () => {
    const height = app?.viewportStableHeight || window.innerHeight;
    document.documentElement.style.setProperty("--tg-viewport", `${height}px`);
    const inset = app?.contentSafeAreaInset ?? app?.safeAreaInset;
    document.documentElement.style.setProperty(
      "--tg-safe-top",
      `${inset?.top ?? 0}px`,
    );
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
