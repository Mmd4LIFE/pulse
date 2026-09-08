"""Account lifecycle and the follow graph."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.telegram import TelegramUser
from app.models import Block, Follow, Notification, NotificationType, User
from app.schemas.user import RESERVED_USERNAMES, USERNAME_RE, UserUpdate

_SANITISE_RE = re.compile(r"[^A-Za-z0-9_]")


async def _username_is_free(db: AsyncSession, username: str) -> bool:
    existing = await db.scalar(
        select(User.id).where(func.lower(User.username) == username.lower())
    )
    return existing is None


async def allocate_username(db: AsyncSession, telegram: TelegramUser) -> str:
    """Pick a free handle, preferring the user's Telegram username."""
    candidates: list[str] = []
    if telegram.username:
        candidates.append(_SANITISE_RE.sub("", telegram.username)[:32])
    if telegram.first_name:
        candidates.append(_SANITISE_RE.sub("", telegram.first_name)[:24])

    for base in candidates:
        if len(base) >= 3 and base.lower() not in RESERVED_USERNAMES:
            if await _username_is_free(db, base):
                return base
            for suffix in range(1, 100):
                candidate = f"{base[: 32 - len(str(suffix))]}{suffix}"
                if await _username_is_free(db, candidate):
                    return candidate

    # Telegram ids are unique, so this always terminates.
    fallback = f"user{telegram.id}"[:32]
    if await _username_is_free(db, fallback):
        return fallback
    for suffix in range(1, 1000):
        candidate = f"{fallback[: 32 - len(str(suffix))]}{suffix}"
        if await _username_is_free(db, candidate):
            return candidate
    raise ConflictError("Could not allocate a username.")


async def get_by_id(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError("Account not found.")
    return user


async def get_by_username(db: AsyncSession, username: str) -> User:
    user = await db.scalar(
        select(User).where(func.lower(User.username) == username.lower())
    )
    if user is None or not user.is_active:
        raise NotFoundError("Account not found.")
    return user


async def get_or_create_from_telegram(
    db: AsyncSession, telegram: TelegramUser
) -> tuple[User, bool]:
    """Return the account for this Telegram id, creating it on first sight."""
    user = await db.scalar(select(User).where(User.telegram_id == telegram.id))
    now = datetime.now(UTC)

    if user is not None:
        # Refresh the fields Telegram owns; leave Pulse-owned profile fields be.
        user.telegram_username = telegram.username
        user.language_code = telegram.language_code
        user.is_telegram_premium = telegram.is_premium
        if telegram.photo_url:
            user.avatar_url = telegram.photo_url
        user.last_seen_at = now
        await db.commit()
        await db.refresh(user)
        return user, False

    user = User(
        telegram_id=telegram.id,
        username=await allocate_username(db, telegram),
        display_name=telegram.display_name[:64],
        telegram_username=telegram.username,
        language_code=telegram.language_code,
        is_telegram_premium=telegram.is_premium,
        avatar_url=telegram.photo_url,
        last_seen_at=now,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Two concurrent first-logins for the same Telegram id: the other one won.
        await db.rollback()
        existing = await db.scalar(select(User).where(User.telegram_id == telegram.id))
        if existing is None:
            raise
        return existing, False

    await db.refresh(user)
    return user, True


async def update_profile(db: AsyncSession, user: User, payload: UserUpdate) -> User:
    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    new_username = data.pop("username", None)
    if new_username and new_username.lower() != user.username.lower():
        if not USERNAME_RE.match(new_username):
            raise ConflictError("That username is not valid.")
        if not await _username_is_free(db, new_username):
            raise ConflictError("That username is already taken.")
        user.username = new_username

    for field, value in data.items():
        setattr(user, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("That username is already taken.") from None
    await db.refresh(user)
    return user


async def is_blocked_either_way(db: AsyncSession, a_id: int, b_id: int) -> bool:
    hit = await db.scalar(
        select(Block.blocker_id).where(
            ((Block.blocker_id == a_id) & (Block.blocked_id == b_id))
            | ((Block.blocker_id == b_id) & (Block.blocked_id == a_id))
        )
    )
    return hit is not None


async def follow(db: AsyncSession, follower: User, followee_id: int) -> bool:
    """Follow an account. Returns False when the edge already existed."""
    if follower.id == followee_id:
        raise PermissionDeniedError("You cannot follow yourself.")

    followee = await get_by_id(db, followee_id)
    if await is_blocked_either_way(db, follower.id, followee_id):
        raise PermissionDeniedError("You cannot follow this account.")

    db.add(Follow(follower_id=follower.id, followee_id=followee_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    await db.execute(
        update(User)
        .where(User.id == follower.id)
        .values(following_count=User.following_count + 1)
    )
    await db.execute(
        update(User)
        .where(User.id == followee_id)
        .values(followers_count=User.followers_count + 1)
    )
    db.add(
        Notification(
            recipient_id=followee.id,
            actor_id=follower.id,
            type=NotificationType.FOLLOW,
        )
    )
    await db.commit()
    return True


async def unfollow(db: AsyncSession, follower: User, followee_id: int) -> bool:
    result = await db.execute(
        delete(Follow).where(
            Follow.follower_id == follower.id, Follow.followee_id == followee_id
        )
    )
    if result.rowcount == 0:
        await db.rollback()
        return False

    await db.execute(
        update(User)
        .where(User.id == follower.id, User.following_count > 0)
        .values(following_count=User.following_count - 1)
    )
    await db.execute(
        update(User)
        .where(User.id == followee_id, User.followers_count > 0)
        .values(followers_count=User.followers_count - 1)
    )
    await db.commit()
    return True


async def block(db: AsyncSession, blocker: User, blocked_id: int) -> bool:
    if blocker.id == blocked_id:
        raise PermissionDeniedError("You cannot block yourself.")
    await get_by_id(db, blocked_id)

    db.add(Block(blocker_id=blocker.id, blocked_id=blocked_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    # A block tears down the follow edges in both directions.
    for a, b in ((blocker.id, blocked_id), (blocked_id, blocker.id)):
        removed = await db.execute(
            delete(Follow).where(Follow.follower_id == a, Follow.followee_id == b)
        )
        if removed.rowcount:
            await db.execute(
                update(User)
                .where(User.id == a, User.following_count > 0)
                .values(following_count=User.following_count - 1)
            )
            await db.execute(
                update(User)
                .where(User.id == b, User.followers_count > 0)
                .values(followers_count=User.followers_count - 1)
            )
    await db.commit()
    return True


async def unblock(db: AsyncSession, blocker: User, blocked_id: int) -> bool:
    result = await db.execute(
        delete(Block).where(Block.blocker_id == blocker.id, Block.blocked_id == blocked_id)
    )
    await db.commit()
    return result.rowcount > 0


async def blocked_ids(db: AsyncSession, user_id: int) -> list[int]:
    """Ids hidden from ``user_id``: everyone they block and everyone blocking them."""
    rows = (
        await db.execute(
            select(Block.blocker_id, Block.blocked_id).where(
                (Block.blocker_id == user_id) | (Block.blocked_id == user_id)
            )
        )
    ).all()
    return [b if a == user_id else a for a, b in rows]


async def list_followers(
    db: AsyncSession, user_id: int, limit: int, cursor: int | None
) -> list[User]:
    stmt = (
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.followee_id == user_id, User.is_active.is_(True))
        .order_by(User.id.desc())
        .limit(limit)
    )
    if cursor:
        stmt = stmt.where(User.id < cursor)
    return list((await db.scalars(stmt)).all())


async def list_following(
    db: AsyncSession, user_id: int, limit: int, cursor: int | None
) -> list[User]:
    stmt = (
        select(User)
        .join(Follow, Follow.followee_id == User.id)
        .where(Follow.follower_id == user_id, User.is_active.is_(True))
        .order_by(User.id.desc())
        .limit(limit)
    )
    if cursor:
        stmt = stmt.where(User.id < cursor)
    return list((await db.scalars(stmt)).all())


async def suggestions(db: AsyncSession, viewer: User | None, limit: int) -> list[User]:
    """Accounts worth following: the most-followed ones the viewer is missing."""
    stmt = (
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.followers_count.desc(), User.id.desc())
        .limit(limit)
    )
    if viewer is not None:
        already = select(Follow.followee_id).where(Follow.follower_id == viewer.id)
        hidden = await blocked_ids(db, viewer.id)
        stmt = stmt.where(User.id != viewer.id, User.id.not_in(already))
        if hidden:
            stmt = stmt.where(User.id.not_in(hidden))
    return list((await db.scalars(stmt)).all())
