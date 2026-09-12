"""Application settings, loaded from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# ``NoDecode`` stops pydantic-settings from JSON-parsing these fields, so they
# can be written as a plain comma-separated string in .env and decoded by the
# validator on Settings instead.
CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    PROJECT_NAME: str = "Pulse"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # Public origin of the Mini App, used for links the bot sends out.
    PUBLIC_WEB_URL: str = "http://localhost:3000"

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_TTL_MINUTES: int = 60
    REFRESH_TOKEN_TTL_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # Reject Telegram initData older than this. Telegram recommends a short
    # window because initData is replayable until it expires.
    TELEGRAM_INITDATA_MAX_AGE_SECONDS: int = 86400

    CORS_ORIGINS: CsvList = ["http://localhost:3000"]

    # --- Telegram ----------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str = ""
    # Set to allow unsigned logins in local development only. Never in prod.
    ALLOW_DEV_LOGIN: bool = False

    # --- Database ----------------------------------------------------------
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "pulse"
    POSTGRES_PASSWORD: str = "pulse"
    POSTGRES_DB: str = "pulse"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Redis -------------------------------------------------------------
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Media -------------------------------------------------------------
    MEDIA_ROOT: str = "/data/media"
    MEDIA_URL_PREFIX: str = "/media"
    MAX_UPLOAD_BYTES: int = 8 * 1024 * 1024
    ALLOWED_IMAGE_TYPES: CsvList = ["image/jpeg", "image/png", "image/webp", "image/gif"]

    # --- Automated accounts ------------------------------------------------
    # Off unless explicitly switched on, so a deployment never starts spending
    # on generation by accident.
    AI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_TIMEOUT_SECONDS: float = 45.0

    # How often the worker wakes to see which accounts are due to act.
    AI_TICK_SECONDS: int = 60
    # Ceilings. The per-account one bounds how chatty any single account can
    # be; the daily one bounds the bill no matter how many accounts exist.
    AI_MAX_POSTS_PER_ACCOUNT_PER_DAY: int = 12
    AI_MAX_GENERATIONS_PER_DAY: int = 600
    # How many accounts get a turn per tick. Without a bound, a tick over
    # hundreds of accounts would run longer than the interval between ticks and
    # they would overlap. Accounts are taken least-recently-acted first, so
    # everyone comes round in turn.
    AI_ACCOUNTS_PER_TICK: int = 20

    # How far back an account will look for something to reply to or like.
    AI_TIMELINE_LOOKBACK_HOURS: int = 48

    # --- Domain rules ------------------------------------------------------
    MAX_PULSE_LENGTH: int = 280
    MAX_MEDIA_PER_PULSE: int = 4
    RATE_LIMIT_PULSES_PER_HOUR: int = 60

    @field_validator("CORS_ORIGINS", "ALLOWED_IMAGE_TYPES", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SYNC_DATABASE_URI(self) -> str:
        """Alembic runs its migrations over a synchronous driver."""
        return self.SQLALCHEMY_DATABASE_URI.replace("+asyncpg", "+psycopg")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
