/**
 * Finding the @mention being typed, so the composer can offer completions.
 *
 * Everything here works off the caret rather than the whole string: only the
 * token immediately before the cursor is a candidate, so editing earlier text
 * never reopens a suggestion list somewhere else in the pulse.
 */

export interface ActiveMention {
  /** What has been typed after the "@", possibly empty. */
  query: string;
  /** Index of the "@" itself. */
  start: number;
  /** Index just past the typed characters, i.e. the caret. */
  end: number;
}

// The "@" has to start a word: an email address or a second "@" is not a
// mention. Telegram handles are letters, digits and underscore, up to 32.
const ACTIVE_MENTION_RE = /(?:^|[^\w@/])@([A-Za-z0-9_]{0,32})$/;

export function findActiveMention(value: string, caret: number): ActiveMention | null {
  const before = value.slice(0, caret);
  const match = ACTIVE_MENTION_RE.exec(before);
  if (!match) return null;

  const query = match[1] ?? "";
  return { query, start: caret - query.length - 1, end: caret };
}

/** Replace the token being typed with a complete handle, and report the caret. */
export function applyMention(
  value: string,
  active: ActiveMention,
  username: string,
): { text: string; caret: number } {
  const before = value.slice(0, active.start);
  const after = value.slice(active.end);
  // A trailing space, unless the next character already is one.
  const spacer = after.startsWith(" ") ? "" : " ";
  const inserted = `@${username}${spacer}`;
  return { text: `${before}${inserted}${after}`, caret: before.length + inserted.length };
}
