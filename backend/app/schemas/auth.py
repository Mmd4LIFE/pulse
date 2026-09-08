"""Authentication payloads."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.user import UserMe


class TelegramLoginRequest(BaseModel):
    init_data: str = Field(
        ...,
        description="Raw window.Telegram.WebApp.initData query string.",
        max_length=8192,
    )


class DevLoginRequest(BaseModel):
    """Local-development shortcut. Disabled unless ALLOW_DEV_LOGIN is set."""

    telegram_id: int
    username: str | None = None
    display_name: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(TokenPair):
    user: UserMe
    is_new_user: bool = False
