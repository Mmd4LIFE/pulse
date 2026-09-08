"use client";

/**
 * Establishes the session.
 *
 * On mount the app hands Telegram's signed `initData` to the backend, which
 * verifies it and returns a token pair. Outside Telegram it falls back to a
 * development login, which the backend refuses unless ALLOW_DEV_LOGIN is set.
 */

import * as React from "react";

import { ApiError, api, tokens } from "@/lib/api";
import {
  applyTelegramTheme,
  getWebApp,
  initialiseWebApp,
  trackViewport,
  waitForWebApp,
} from "@/lib/telegram";
import type { UserMe } from "@/types/api";

type Status = "loading" | "ready" | "error";

interface AuthContextValue {
  user: UserMe | null;
  status: Status;
  error: string | null;
  isNewUser: boolean;
  refresh: () => Promise<void>;
  setUser: (user: UserMe) => void;
  retry: () => void;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

const DEV_ID_KEY = "pulse.dev_telegram_id";

/** Raised when the app is opened in a plain browser in production. */
class OutsideTelegramError extends Error {
  constructor() {
    super("Pulse must be opened from inside Telegram.");
    this.name = "OutsideTelegramError";
  }
}

/** A stable pretend Telegram id, so browser reloads keep the same dev account. */
function developmentTelegramId(): number {
  try {
    const saved = localStorage.getItem(DEV_ID_KEY);
    if (saved) return Number(saved);
    const fresh = Math.floor(900_000_000 + Math.random() * 90_000_000);
    localStorage.setItem(DEV_ID_KEY, String(fresh));
    return fresh;
  } catch {
    return 900_000_001;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserMe | null>(null);
  const [status, setStatus] = React.useState<Status>("loading");
  const [error, setError] = React.useState<string | null>(null);
  const [isNewUser, setIsNewUser] = React.useState(false);
  const [attempt, setAttempt] = React.useState(0);

  React.useEffect(() => {
    initialiseWebApp();
    applyTelegramTheme();
    const stopTracking = trackViewport();

    const app = getWebApp();
    const onTheme = () => applyTelegramTheme();
    app?.onEvent("themeChanged", onTheme);

    // Outside Telegram the OS preference is what drives the theme, so follow it.
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    media?.addEventListener("change", onTheme);

    return () => {
      app?.offEvent("themeChanged", onTheme);
      media?.removeEventListener("change", onTheme);
      stopTracking();
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    async function signIn() {
      setStatus("loading");
      setError(null);

      try {
        // An existing refresh token beats re-doing the handshake.
        if (tokens.hasRefresh()) {
          try {
            const existing = await api.me();
            if (!cancelled) {
              setUser(existing);
              setStatus("ready");
            }
            return;
          } catch {
            tokens.clear();
          }
        }

        // Wait for the Telegram bridge before deciding where we are: reading
        // initData too early looks identical to "not in Telegram", and in
        // production that path ends at a disabled dev login.
        const app = await waitForWebApp();
        const initData = app?.initData;

        if (!initData && process.env.NODE_ENV === "production") {
          // Being outside Telegram is a normal thing to explain, not a crash.
          throw new OutsideTelegramError();
        }

        const session = initData
          ? await api.loginWithTelegram(initData)
          : await api.loginForDevelopment(developmentTelegramId());

        tokens.setSession(session);
        if (cancelled) return;
        setUser(session.user);
        setIsNewUser(session.is_new_user);
        setStatus("ready");
      } catch (err) {
        if (cancelled) return;
        let message = "Could not reach Pulse. Check your connection and try again.";
        if (err instanceof OutsideTelegramError) {
          message =
            "Pulse runs inside Telegram. Open it from @tlgrmpulse_bot — tap the menu button, or send /start.";
        } else if (err instanceof ApiError) {
          message = err.message;
        }
        setError(message);
        setStatus("error");
      }
    }

    void signIn();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const refresh = React.useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      /* keep the last known profile */
    }
  }, []);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      error,
      isNewUser,
      refresh,
      setUser,
      retry: () => setAttempt((n) => n + 1),
    }),
    [user, status, error, isNewUser, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

/** The signed-in user, for the many components that cannot render without one. */
export function useCurrentUser(): UserMe {
  const { user } = useAuth();
  if (!user) throw new Error("useCurrentUser used before the session was ready");
  return user;
}
