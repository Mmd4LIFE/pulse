"""Authentication: exchange Telegram initData for a token pair."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.telegram import (
    InitDataError,
    TelegramUser,
    diagnose,
    verify_init_data,
)
from app.schemas.auth import (
    AuthResponse,
    DevLoginRequest,
    RefreshRequest,
    TelegramLoginRequest,
    TokenPair,
)
from app.schemas.user import UserMe
from app.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)


async def _me(db, user) -> UserMe:
    """The caller's own profile, including the counts only they can see."""
    out = UserMe.model_validate(user)
    out.pending_follow_requests = await user_service.pending_request_count(db, user.id)
    return out


def _token_pair(user_id: int) -> dict[str, object]:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_TTL_MINUTES * 60,
    }


@router.post("/telegram", response_model=AuthResponse)
async def login_with_telegram(payload: TelegramLoginRequest, db: DbSession) -> AuthResponse:
    """Verify the Mini App's signed initData and issue a session."""
    try:
        init_data = verify_init_data(
            payload.init_data,
            settings.TELEGRAM_BOT_TOKEN,
            max_age_seconds=settings.TELEGRAM_INITDATA_MAX_AGE_SECONDS,
        )
    except InitDataError as exc:
        # The reason is logged but not returned: a probing client learns only
        # that the handshake failed.
        log.warning(
            "initdata_rejected",
            reason=str(exc),
            **diagnose(payload.init_data, settings.TELEGRAM_BOT_TOKEN),
        )
        raise AuthenticationError("Telegram sign-in could not be verified.") from exc

    user, created = await user_service.get_or_create_from_telegram(db, init_data.user)
    log.info("login", user_id=user.id, new=created)

    return AuthResponse(
        **_token_pair(user.id),
        user=await _me(db, user),
        is_new_user=created,
    )


@router.post("/dev", response_model=AuthResponse)
async def login_for_development(payload: DevLoginRequest, db: DbSession) -> AuthResponse:
    """Sign in without Telegram. Only available when ALLOW_DEV_LOGIN is set."""
    if not settings.ALLOW_DEV_LOGIN or settings.is_production:
        raise PermissionDeniedError("Development login is disabled.")

    telegram_user = TelegramUser(
        id=payload.telegram_id,
        first_name=payload.display_name or f"Dev {payload.telegram_id}",
        username=payload.username,
    )
    user, created = await user_service.get_or_create_from_telegram(db, telegram_user)
    return AuthResponse(
        **_token_pair(user.id),
        user=await _me(db, user),
        is_new_user=created,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_session(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        user_id = decode_token(payload.refresh_token, "refresh")
    except TokenError as exc:
        raise AuthenticationError(
            "Your session has expired. Please reopen the app."
        ) from exc

    user = await user_service.get_by_id(db, user_id)
    return TokenPair(**_token_pair(user.id))


@router.get("/me", response_model=UserMe, status_code=status.HTTP_200_OK)
async def read_current_user(user: CurrentUser, db: DbSession) -> UserMe:
    return await _me(db, user)
