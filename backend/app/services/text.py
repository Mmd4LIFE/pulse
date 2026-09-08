"""Extraction of entities from pulse text."""

from __future__ import annotations

import re

# A hashtag must start with a letter so that "#1" stays a plain number.
HASHTAG_RE = re.compile(r"(?<![\w&/])#([A-Za-z؀-ۿ][\w؀-ۿ]{0,63})")
MENTION_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9_]{3,32})(?!\w)")
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)

MAX_HASHTAGS = 10
MAX_MENTIONS = 10


def extract_hashtags(text: str) -> list[str]:
    """Return case-folded, de-duplicated tags in order of first appearance."""
    seen: dict[str, None] = {}
    for match in HASHTAG_RE.finditer(text):
        seen.setdefault(match.group(1).lower(), None)
    return list(seen)[:MAX_HASHTAGS]


def extract_mentions(text: str) -> list[str]:
    """Return case-folded, de-duplicated usernames in order of appearance."""
    seen: dict[str, None] = {}
    for match in MENTION_RE.finditer(text):
        seen.setdefault(match.group(1).lower(), None)
    return list(seen)[:MAX_MENTIONS]


def normalise_content(text: str) -> str:
    """Trim edges and collapse runs of blank lines to at most two."""
    cleaned = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n"))
    return cleaned.strip()
