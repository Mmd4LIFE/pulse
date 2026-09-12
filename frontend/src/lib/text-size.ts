/**
 * The reader's text size.
 *
 * The account is the source of truth so the choice follows someone between
 * devices, but the last value is also mirrored into localStorage and applied
 * before the session resolves — otherwise every cold start would paint at the
 * default size and visibly reflow once the profile arrived.
 */

export type TextSize = "small" | "medium" | "large" | "xlarge";

export const TEXT_SIZES: { value: TextSize; label: string; scale: number }[] = [
  { value: "small", label: "Small", scale: 0.875 },
  { value: "medium", label: "Medium", scale: 1 },
  { value: "large", label: "Large", scale: 1.125 },
  { value: "xlarge", label: "Extra large", scale: 1.25 },
];

export const DEFAULT_TEXT_SIZE: TextSize = "small";

const STORAGE_KEY = "pulse.text_size";

export function scaleFor(size: TextSize): number {
  return TEXT_SIZES.find((s) => s.value === size)?.scale ?? 0.875;
}

export function isTextSize(value: unknown): value is TextSize {
  return TEXT_SIZES.some((s) => s.value === value);
}

export function applyTextSize(size: TextSize): void {
  if (typeof document === "undefined") return;
  document.documentElement.style.setProperty("--text-scale", String(scaleFor(size)));
  try {
    localStorage.setItem(STORAGE_KEY, size);
  } catch {
    /* private mode */
  }
}

/** The last known choice, for painting correctly before the profile loads. */
export function cachedTextSize(): TextSize {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isTextSize(stored)) return stored;
  } catch {
    /* private mode */
  }
  return DEFAULT_TEXT_SIZE;
}
