"""JWT issuing and verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

TokenType = Literal["access", "refresh"]

ISSUER = "pulse"


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or of the wrong type."""


def _create_token(subject: str | int, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "typ": token_type,
        "iss": ISSUER,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | int) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    )


def create_refresh_token(subject: str | int) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    )


def decode_token(token: str, expected_type: TokenType) -> int:
    """Return the user id encoded in ``token``, or raise ``TokenError``."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "typ"]},
        )
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("typ") != expected_type:
        raise TokenError(f"expected a {expected_type} token")

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("token subject is not a user id") from exc
