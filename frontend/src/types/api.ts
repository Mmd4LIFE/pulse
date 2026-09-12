/** Response shapes returned by the Pulse API. Mirrors the backend schemas. */

export interface UserSummary {
  id: number;
  username: string;
  display_name: string;
  avatar_url: string | null;
  is_verified: boolean;
}

export interface UserPublic extends UserSummary {
  is_private: boolean;
  /** The caller has asked, but not yet been allowed, to follow. */
  follow_requested: boolean;
  /** Whether the caller may read this account's pulses at all. */
  can_view_pulses: boolean;
  bio: string | null;
  location: string | null;
  website: string | null;
  banner_url: string | null;
  followers_count: number;
  following_count: number;
  pulses_count: number;
  created_at: string;
  is_following: boolean;
  is_followed_by: boolean;
  is_blocked: boolean;
}

export interface UserMe extends UserPublic {
  text_size: "small" | "medium" | "large" | "xlarge";
  telegram_id: number;
  language_code: string | null;
  is_telegram_premium: boolean;
  pending_follow_requests: number;
}

export interface MediaItem {
  id: number;
  url: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  alt_text: string | null;
}

export interface PulseRef {
  id: number;
  content: string;
  author: UserSummary;
  created_at: string;
  media: MediaItem[];
  is_deleted: boolean;
}

export interface Pulse {
  id: number;
  content: string;
  author: UserSummary;
  created_at: string;
  reply_to_id: number | null;
  quote_of_id: number | null;
  like_count: number;
  reply_count: number;
  repulse_count: number;
  quote_count: number;
  bookmark_count: number;
  view_count: number;
  media: MediaItem[];
  quote_of: PulseRef | null;
  reply_to: PulseRef | null;
  is_liked: boolean;
  is_repulsed: boolean;
  is_bookmarked: boolean;
  is_mine: boolean;
  repulsed_by: UserSummary | null;
  sent_to_channel: boolean;
}

export interface Thread {
  ancestors: Pulse[];
  pulse: Pulse;
  replies: Pulse[];
  replies_next_cursor: string | null;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export type NotificationType =
  | "like"
  | "reply"
  | "repulse"
  | "quote"
  | "follow"
  | "mention"
  | "follow_request";

export interface AppNotification {
  id: number;
  type: NotificationType;
  actor: UserSummary;
  pulse: PulseRef | null;
  is_read: boolean;
  created_at: string;
}

export interface Trend {
  tag: string;
  pulse_count: number;
  rank: number;
}

export interface SearchResults {
  users: UserPublic[];
  pulses: Pulse[];
  hashtags: { tag: string; usage_count: number }[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse extends TokenPair {
  user: UserMe;
  is_new_user: boolean;
}

export interface ConnectedChannel {
  id: number;
  chat_id: number;
  username: string | null;
  title: string;
  can_post: boolean;
  last_error: string | null;
  last_posted_at: string | null;
}
