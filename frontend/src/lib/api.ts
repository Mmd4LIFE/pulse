/**
 * HTTP client for the Pulse API.
 *
 * Holds the access token in memory and the refresh token in localStorage, and
 * transparently retries a single time after refreshing an expired session so
 * that callers never have to think about token lifetime.
 */

import type {
  AppNotification,
  AuthResponse,
  ConnectedChannel,
  MediaItem,
  Page,
  Pulse,
  SearchResults,
  Thread,
  TokenPair,
  Trend,
  UserMe,
  UserPublic,
  UserSummary,
} from "@/types/api";

import type { TextSize } from "@/lib/text-size";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";
const REFRESH_KEY = "pulse.refresh_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;

export const tokens = {
  setSession(pair: TokenPair): void {
    accessToken = pair.access_token;
    try {
      localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    } catch {
      /* private mode */
    }
  },
  clear(): void {
    accessToken = null;
    try {
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* private mode */
    }
  },
  hasRefresh(): boolean {
    try {
      return Boolean(localStorage.getItem(REFRESH_KEY));
    } catch {
      return false;
    }
  },
  get access(): string | null {
    return accessToken;
  },
};

async function refreshSession(): Promise<boolean> {
  // Collapse concurrent 401s into one refresh call.
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(REFRESH_KEY);
    } catch {
      stored = null;
    }
    if (!stored) return false;

    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: stored }),
      });
      if (!response.ok) {
        tokens.clear();
        return false;
      }
      tokens.setSession((await response.json()) as TokenPair);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "error";
  let message = "Something went wrong.";
  try {
    const body = await response.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    } else if (body?.detail) {
      message = typeof body.detail === "string" ? body.detail : message;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(response.status, code, message);
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  auth?: boolean;
  retry?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = true, retry = true, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  let payload: BodyInit | undefined;

  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }

  if (auth && accessToken) {
    finalHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: payload,
  });

  if (response.status === 401 && auth && retry) {
    if (await refreshSession()) {
      return request<T>(path, { ...options, retry: false });
    }
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const query = (params: Record<string, string | number | boolean | null | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
};

export interface PageQuery {
  cursor?: string | null;
  limit?: number;
}

export const api = {
  // --- auth ---------------------------------------------------------------
  loginWithTelegram: (initData: string) =>
    request<AuthResponse>("/auth/telegram", {
      method: "POST",
      body: { init_data: initData },
      auth: false,
    }),

  loginForDevelopment: (telegramId: number, username?: string, displayName?: string) =>
    request<AuthResponse>("/auth/dev", {
      method: "POST",
      body: { telegram_id: telegramId, username, display_name: displayName },
      auth: false,
    }),

  me: () => request<UserMe>("/auth/me"),

  updateProfile: (patch: Partial<Record<string, string>>) =>
    request<UserMe>("/users/me", { method: "PATCH", body: patch }),

  // --- feeds --------------------------------------------------------------
  homeFeed: (p: PageQuery = {}) => request<Page<Pulse>>(`/feed/home${query({ ...p })}`),
  exploreFeed: (p: PageQuery = {}) =>
    request<Page<Pulse>>(`/feed/explore${query({ ...p })}`),
  bookmarks: (p: PageQuery = {}) =>
    request<Page<Pulse>>(`/feed/bookmarks${query({ ...p })}`),
  trends: (limit = 10) => request<Trend[]>(`/feed/trends${query({ limit })}`),
  hashtagFeed: (tag: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/feed/hashtag/${encodeURIComponent(tag)}${query({ ...p })}`),

  // --- pulses -------------------------------------------------------------
  createPulse: (input: {
    content: string;
    reply_to_id?: number;
    quote_of_id?: number;
    media_ids?: number[];
    post_to_channel?: boolean;
  }) => request<Pulse>("/pulses", { method: "POST", body: input }),

  getPulse: (id: number) => request<Pulse>(`/pulses/${id}`),
  getThread: (id: number, p: PageQuery = {}) =>
    request<Thread>(`/pulses/${id}/thread${query({ ...p })}`),
  getReplies: (id: number, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/pulses/${id}/replies${query({ ...p })}`),
  deletePulse: (id: number) => request<void>(`/pulses/${id}`, { method: "DELETE" }),

  like: (id: number) => request<void>(`/pulses/${id}/like`, { method: "POST" }),
  unlike: (id: number) => request<void>(`/pulses/${id}/like`, { method: "DELETE" }),
  repulse: (id: number) => request<void>(`/pulses/${id}/repulse`, { method: "POST" }),
  unrepulse: (id: number) => request<void>(`/pulses/${id}/repulse`, { method: "DELETE" }),
  bookmark: (id: number) => request<void>(`/pulses/${id}/bookmark`, { method: "POST" }),
  unbookmark: (id: number) =>
    request<void>(`/pulses/${id}/bookmark`, { method: "DELETE" }),

  // --- people -------------------------------------------------------------
  getUser: (username: string) =>
    request<UserPublic>(`/users/${encodeURIComponent(username)}`),
  follow: (username: string) =>
    request<void>(`/users/${encodeURIComponent(username)}/follow`, { method: "POST" }),
  unfollow: (username: string) =>
    request<void>(`/users/${encodeURIComponent(username)}/follow`, { method: "DELETE" }),
  block: (username: string) =>
    request<void>(`/users/${encodeURIComponent(username)}/block`, { method: "POST" }),
  unblock: (username: string) =>
    request<void>(`/users/${encodeURIComponent(username)}/block`, { method: "DELETE" }),
  suggestions: (limit = 5) =>
    request<UserPublic[]>(`/users/suggestions${query({ limit })}`),

  // --- privacy & follow requests -----------------------------------------
  setTextSize: (size: TextSize) =>
    request<UserMe>("/users/me/appearance", {
      method: "PUT",
      body: { text_size: size },
    }),

  setPrivacy: (isPrivate: boolean) =>
    request<UserMe>("/users/me/privacy", {
      method: "PUT",
      body: { is_private: isPrivate },
    }),

  followRequests: (p: PageQuery = {}) =>
    request<Page<UserPublic>>(`/users/me/follow-requests${query({ ...p })}`),
  followRequestCount: () =>
    request<{ count: number }>("/users/me/follow-requests/count"),
  approveFollowRequest: (username: string) =>
    request<void>(
      `/users/me/follow-requests/${encodeURIComponent(username)}/approve`,
      { method: "POST" },
    ),
  declineFollowRequest: (username: string) =>
    request<void>(
      `/users/me/follow-requests/${encodeURIComponent(username)}/decline`,
      { method: "POST" },
    ),

  // --- connected channel --------------------------------------------------
  myChannel: () => request<ConnectedChannel | null>("/channels/me"),
  connectChannel: (reference: string) =>
    request<ConnectedChannel>("/channels/me", {
      method: "PUT",
      body: { reference },
    }),
  disconnectChannel: () => request<void>("/channels/me", { method: "DELETE" }),
  testChannel: () => request<{ message: string }>("/channels/me/test", { method: "POST" }),

  userPulses: (username: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/users/${encodeURIComponent(username)}/pulses${query({ ...p })}`),
  userReplies: (username: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/users/${encodeURIComponent(username)}/replies${query({ ...p })}`),
  userMedia: (username: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/users/${encodeURIComponent(username)}/media${query({ ...p })}`),
  userLikes: (username: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/users/${encodeURIComponent(username)}/likes${query({ ...p })}`),
  followers: (username: string, p: PageQuery = {}) =>
    request<Page<UserPublic>>(
      `/users/${encodeURIComponent(username)}/followers${query({ ...p })}`,
    ),
  following: (username: string, p: PageQuery = {}) =>
    request<Page<UserPublic>>(
      `/users/${encodeURIComponent(username)}/following${query({ ...p })}`,
    ),

  // --- search & notifications --------------------------------------------
  search: (q: string) => request<SearchResults>(`/search${query({ q })}`),
  searchPulses: (q: string, p: PageQuery = {}) =>
    request<Page<Pulse>>(`/search/pulses${query({ q, ...p })}`),
  searchUsers: (q: string, p: PageQuery = {}) =>
    request<Page<UserPublic>>(`/search/users${query({ q, ...p })}`),
  suggestMentions: (q: string, limit = 6) =>
    request<UserSummary[]>(`/search/mentions${query({ q, limit })}`),

  notifications: (p: PageQuery = {}) =>
    request<Page<AppNotification>>(`/notifications${query({ ...p })}`),
  unreadCount: () => request<{ count: number }>("/notifications/unread-count"),
  markAllRead: () => request<{ count: number }>("/notifications/read-all", { method: "POST" }),

  // --- media --------------------------------------------------------------
  uploadImage: (file: File, altText?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (altText) form.append("alt_text", altText);
    return request<MediaItem>("/media", { method: "POST", body: form });
  },
};
