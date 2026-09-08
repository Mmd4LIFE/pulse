"""Shared FastAPI dependencies."""

# No ``from __future__ import annotations`` here: FastAPI resolves the
# Annotated metadata on the Pagination class at runtime, and postponed
# annotations turn those into unresolvable nested forward references.

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models import User

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def _user_from_token(db: AsyncSession, token: str) -> User:
    try:
        user_id = decode_token(token, "access")
    except TokenError as exc:
        raise AuthenticationError(
            "Your session is not valid. Please reopen the app."
        ) from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("This account is no longer available.")
    return user


async def get_current_user(db: DbSession, credentials: BearerToken) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Sign in to continue.")
    user = await _user_from_token(db, credentials.credentials)

    # Cheap liveness signal; only written once a minute per user.
    now = datetime.now(UTC)
    if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() > 60:
        user.last_seen_at = now
        await db.commit()
    return user


async def get_optional_user(db: DbSession, credentials: BearerToken) -> User | None:
    """Resolve the caller when a token is present, without ever rejecting."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return await _user_from_token(db, credentials.credentials)
    except AuthenticationError:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


class Pagination:
    """Cursor pagination shared by every list endpoint."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        cursor: Annotated[str | None, Query(max_length=32)] = None,
    ) -> None:
        self.limit = limit
        self.cursor = self._parse(cursor)

    @staticmethod
    def _parse(cursor: str | None) -> int | None:
        if not cursor:
            return None
        try:
            value = int(cursor)
        except ValueError:
            # A malformed cursor reads as "start from the beginning" rather
            # than failing the whole request.
            return None
        return value if value > 0 else None


Paging = Annotated[Pagination, Depends(Pagination)]


def client_ip(request: Request) -> str:
    """Best-effort client address, trusting the reverse proxy in front of us."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
