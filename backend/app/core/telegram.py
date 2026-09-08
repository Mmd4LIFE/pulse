"""Validation of Telegram Mini App ``initData``.

The Mini App hands the frontend a signed query string. Everything the backend
believes about who is calling comes from verifying that signature here, so this
module is the trust boundary of the whole application.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

# Fields Telegram signs over are *all* pairs except these two. ``hash`` is the
# signature itself; ``signature`` is the separate Ed25519 third-party signature,
# which is explicitly excluded from the HMAC data-check-string.
_EXCLUDED_FROM_CHECK = frozenset({"hash", "signature"})


class InitDataError(Exception):
    """Raised when initData is malformed, unsigned, forged, or stale."""


@dataclass(frozen=True, slots=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    photo_url: str | None = None
    allows_write_to_pm: bool = False

    @property
    def display_name(self) -> str:
        parts = [self.first_name, self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or f"user{self.id}"


@dataclass(frozen=True, slots=True)
class InitData:
    user: TelegramUser
    auth_date: int
    query_id: str | None = None
    start_param: str | None = None
    chat_type: str | None = None
    chat_instance: str | None = None
    raw: dict[str, str] | None = None


def _parse(init_data: str) -> list[tuple[str, str]]:
    """Split initData the way the browser built it.

    Telegram assembles the string with ``encodeURIComponent``, so values are
    decoded with ``unquote`` rather than form semantics: ``parse_qsl`` would
    additionally turn a literal ``+`` into a space and change the bytes the
    signature was computed over. Blank values are kept, because Telegram signs
    empty fields too and dropping them would alter the check string.
    """
    pairs: list[tuple[str, str]] = []
    for chunk in init_data.split("&"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        pairs.append((unquote(key), unquote(value)))
    return pairs


def _secret_key(bot_token: str) -> bytes:
    """HMAC-SHA256 of the bot token, keyed by the literal string ``WebAppData``."""
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(pairs) if k not in _EXCLUDED_FROM_CHECK)


def diagnose(init_data: str, bot_token: str) -> dict[str, object]:
    """Explain a verification failure without putting the payload in the logs.

    ``initData`` carries the caller's Telegram profile and a hash that stays
    replayable until it expires, so none of it belongs in a log line. Instead
    this reports the *shape* of what arrived and which interpretation of the
    spec — if any — its signature would have satisfied, which is what actually
    identifies a mismatch.
    """
    try:
        decoded = _parse(init_data)
    except Exception:
        return {"parse": "failed"}

    values = dict(decoded)
    received = (values.get("hash") or "").lower()

    # Values exactly as they arrived on the wire, undecoded.
    raw: list[tuple[str, str]] = []
    for chunk in init_data.split("&"):
        key, _, value = chunk.partition("=")
        raw.append((unquote(key), value))

    def check(pairs: list[tuple[str, str]], exclude: frozenset[str]) -> str:
        text = "\n".join(f"{k}={v}" for k, v in sorted(pairs) if k not in exclude)
        return hmac.new(_secret_key(bot_token), text.encode(), hashlib.sha256).hexdigest()

    candidates = {
        # What we do now: decoded values, hash and signature both excluded.
        "decoded_without_signature": check(decoded, _EXCLUDED_FROM_CHECK),
        # Older guidance excluded only the hash.
        "decoded_with_signature": check(decoded, frozenset({"hash"})),
        # A client that hashed the percent-encoded form.
        "raw_without_signature": check(raw, _EXCLUDED_FROM_CHECK),
        "raw_with_signature": check(raw, frozenset({"hash"})),
    }
    matched = [name for name, digest in candidates.items() if digest == received]

    return {
        "fields": sorted(values),
        "matched_interpretation": matched or None,
        "has_signature": "signature" in values,
        "auth_date": values.get("auth_date"),
        "length": len(init_data),
    }


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int | None = 86_400,
) -> InitData:
    """Verify a raw ``initData`` query string and return its parsed contents.

    Raises ``InitDataError`` on any failure. Never returns partially-trusted
    data: if the signature does not check out, nothing is parsed out of it.
    """
    if not init_data:
        raise InitDataError("initData is empty")

    pairs = _parse(init_data)
    if not pairs:
        raise InitDataError("initData is not a valid query string")

    values = dict(pairs)
    received_hash = values.get("hash")
    if not received_hash:
        raise InitDataError("initData is missing its hash")

    expected = hmac.new(
        _secret_key(bot_token),
        _data_check_string(pairs).encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash.lower()):
        raise InitDataError("initData signature does not match")

    raw_auth_date = values.get("auth_date")
    if not raw_auth_date:
        raise InitDataError("initData is missing auth_date")
    try:
        auth_date = int(raw_auth_date)
    except ValueError as exc:
        raise InitDataError("initData auth_date is not an integer") from exc

    if max_age_seconds is not None:
        age = time.time() - auth_date
        if age > max_age_seconds:
            raise InitDataError("initData has expired")
        # Small tolerance for clock skew between Telegram and this host.
        if age < -300:
            raise InitDataError("initData auth_date is in the future")

    raw_user = values.get("user")
    if not raw_user:
        raise InitDataError("initData does not identify a user")
    try:
        user_payload: dict[str, Any] = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise InitDataError("initData user payload is not valid JSON") from exc

    if not isinstance(user_payload.get("id"), int):
        raise InitDataError("initData user payload has no numeric id")

    user = TelegramUser(
        id=user_payload["id"],
        first_name=str(user_payload.get("first_name") or ""),
        last_name=user_payload.get("last_name"),
        username=user_payload.get("username"),
        language_code=user_payload.get("language_code"),
        is_premium=bool(user_payload.get("is_premium", False)),
        photo_url=user_payload.get("photo_url"),
        allows_write_to_pm=bool(user_payload.get("allows_write_to_pm", False)),
    )

    return InitData(
        user=user,
        auth_date=auth_date,
        query_id=values.get("query_id"),
        start_param=values.get("start_param"),
        chat_type=values.get("chat_type"),
        chat_instance=values.get("chat_instance"),
        raw=values,
    )
