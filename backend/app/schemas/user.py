"""User-facing account payloads."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ORMModel

TextSize = Literal["small", "medium", "large", "xlarge"]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
RESERVED_USERNAMES = {
    "admin",
    "api",
    "root",
    "pulse",
    "support",
    "help",
    "settings",
    "about",
    "explore",
    "search",
    "home",
    "notifications",
    "bookmarks",
    "compose",
    "me",
    "login",
    "logout",
    "signup",
    "terms",
    "privacy",
    "static",
    "media",
    "null",
}


class UserPublic(ORMModel):
    """The account as any other user sees it."""

    id: int
    username: str
    display_name: str
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    is_verified: bool = False
    is_private: bool = False
    followers_count: int = 0
    following_count: int = 0
    pulses_count: int = 0
    created_at: datetime

    # Filled in per-request relative to the caller.
    is_following: bool = False
    is_followed_by: bool = False
    is_blocked: bool = False
    # A protected account the caller has asked, but not yet been allowed, to follow.
    follow_requested: bool = False
    # Whether the caller may read this account's pulses at all.
    can_view_pulses: bool = True


class UserMe(UserPublic):
    text_size: TextSize = "small"
    telegram_id: int
    language_code: str | None = None
    is_telegram_premium: bool = False
    pending_follow_requests: int = 0


class UserSummary(ORMModel):
    """Compact form used inside pulses and notification rows."""

    id: int
    username: str
    display_name: str
    avatar_url: str | None = None
    is_verified: bool = False


class PrivacyUpdate(ORMModel):
    is_private: bool


class AppearanceUpdate(ORMModel):
    text_size: TextSize


class UserUpdate(ORMModel):
    username: str | None = Field(default=None, min_length=3, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    bio: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=512)
    banner_url: str | None = Field(default=None, max_length=512)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-32 characters of letters, numbers or underscore."
            )
        if v.lower() in RESERVED_USERNAMES:
            raise ValueError("That username is reserved.")
        return v

    @field_validator("bio", "location", "website", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v
