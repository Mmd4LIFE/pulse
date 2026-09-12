/**
 * Deciding which way a piece of user text runs.
 *
 * `dir="auto"` would be simpler, but it picks the direction from the *first*
 * strong character. A Persian pulse that happens to open with an English brand
 * name would be laid out left-to-right, with its punctuation stranded on the
 * wrong side. Counting the letters instead follows what the text is mostly
 * written in, which is what a reader expects.
 */

export type Direction = "ltr" | "rtl";

// Hebrew, Arabic, Syriac, Thaana, N'Ko, plus the Arabic presentation forms.
const RTL_CHAR = /[֐-׿؀-ۿ܀-ݏހ-޿߀-߿ࡠ-ࣿיִ-﷿ﹰ-﻿]/;
// Latin, Cyrillic and Greek letters count towards left-to-right.
const LTR_CHAR = /[A-Za-zÀ-ʯͰ-ӿḀ-ỿ]/;

// Handles, hashtags and links are written in Latin whatever the language of
// the pulse, so counting them would drag Persian text the wrong way.
const NEUTRAL = /(https?:\/\/\S+)|([@#][A-Za-z0-9_]+)/g;

// Below this share, the minority script is treated as words borrowed into the
// majority's sentence rather than a change of direction.
const OVERRIDE_SHARE = 2 / 3;

export function detectDirection(text: string): Direction {
  if (!text) return "ltr";

  const prose = text.replace(NEUTRAL, " ");

  let rtl = 0;
  let ltr = 0;
  let first: Direction | null = null;

  for (const character of prose) {
    if (RTL_CHAR.test(character)) {
      rtl += 1;
      first ??= "rtl";
    } else if (LTR_CHAR.test(character)) {
      ltr += 1;
      first ??= "ltr";
    }
  }

  // No letters at all: digits, emoji, a bare link.
  if (first === null) return "ltr";

  // The opening sets the direction, because that is where a reader starts. A
  // Persian sentence quoting a few English words stays Persian.
  //
  // It is overridden only when the other script clearly dominates, which is
  // the case that first-character detection gets wrong: a sentence opening
  // with an English product name but written in Persian throughout.
  const letters = rtl + ltr;
  const opposite = first === "rtl" ? ltr : rtl;
  if (opposite / letters >= OVERRIDE_SHARE) return first === "rtl" ? "ltr" : "rtl";

  return first;
}

/** True when the text has any right-to-left letters, mixed or not. */
export function hasRtl(text: string): boolean {
  return RTL_CHAR.test(text);
}
