"""Bot settings, read from the same .env as the rest of the stack."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), extra="ignore", case_sensitive=False
    )

    TELEGRAM_BOT_TOKEN: str = Field(min_length=10)
    PUBLIC_WEB_URL: str = "https://pulse.mammad.site"
    PROJECT_NAME: str = "Pulse"
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()  # type: ignore[call-arg]
