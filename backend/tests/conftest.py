"""Test fixtures.

Tests run against a real PostgreSQL database rather than SQLite: the schema
leans on partial indexes and boolean-to-int casts in CHECK constraints, so a
different engine would not be testing the thing we ship.
"""

from __future__ import annotations

import os

# Point the settings object at the test database before anything imports it.
os.environ.setdefault("POSTGRES_DB", "pulse_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-to-pass")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("ALLOW_DEV_LOGIN", "true")
os.environ.setdefault("LOG_JSON", "false")

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Base, User

# NullPool: pytest-asyncio gives each test its own event loop, and a pooled
# asyncpg connection cannot be handed from one loop to the next.
TEST_ENGINE = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, poolclass=NullPool)
TestSession = async_sessionmaker(TEST_ENGINE, class_=AsyncSession, expire_on_commit=False)

ALL_TABLES = (
    "notifications, mentions, pulse_hashtags, hashtags, media, "
    "bookmarks, likes, blocks, follows, pulses, users"
)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Build the schema once per run.

    Deliberately synchronous: a session-scoped async fixture would need a
    session-scoped event loop, which then conflicts with the per-test loops.
    """
    sync_engine = create_engine(settings.SYNC_DATABASE_URI, poolclass=NullPool)
    with sync_engine.begin() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    sync_engine.dispose()


@pytest.fixture(autouse=True)
async def _clean() -> AsyncIterator[None]:
    """Start every test from an empty database."""
    async with TEST_ENGINE.begin() as conn:
        await conn.execute(text(f"TRUNCATE {ALL_TABLES} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator[AsyncSession]:
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def make_user(db: AsyncSession):
    """Factory that inserts a user directly, bypassing the Telegram handshake."""
    counter = {"n": 0}

    async def _make(username: str | None = None, **kwargs) -> User:
        counter["n"] += 1
        n = counter["n"]
        user = User(
            telegram_id=kwargs.pop("telegram_id", 100_000 + n),
            username=username or f"tester{n}",
            display_name=kwargs.pop("display_name", f"Tester {n}"),
            **kwargs,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    return _make


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def as_user():
    return auth_headers
