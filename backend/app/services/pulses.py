"""Creating, reading, and interacting with pulses."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import settings
from app.core.errors import (
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    ValidationError,
)
from app.models import (
    Bookmark,
    Hashtag,
    Like,
    Media,
    Mention,
    Notification,
    NotificationType,
    Pulse,
    PulseHashtag,
    User,
)
from app.schemas.pulse import PulseCreate
from app.services import users as user_service
from app.services.text import extract_hashtags, extract_mentions, normalise_content


def _load_options() -> tuple:
    """Eager-load everything a rendered pulse needs, one level of nesting deep."""
    return (
        joinedload(Pulse.author),
        selectinload(Pulse.media),
        selectinload(Pulse.quote_of).joinedload(Pulse.author),
        selectinload(Pulse.quote_of).selectinload(Pulse.media),
        selectinload(Pulse.reply_to).joinedload(Pulse.author),
        selectinload(Pulse.reply_to).selectinload(Pulse.media),
        selectinload(Pulse.repulse_of).joinedload(Pulse.author),
        selectinload(Pulse.repulse_of).selectinload(Pulse.media),
        selectinload(Pulse.repulse_of)
        .selectinload(Pulse.quote_of)
        .joinedload(Pulse.author),
        selectinload(Pulse.repulse_of)
        .selectinload(Pulse.quote_of)
        .selectinload(Pulse.media),
    )


def _visible(stmt: Select) -> Select:
    return stmt.where(Pulse.is_deleted.is_(False))


async def _apply_block_filter(
    db: AsyncSession, stmt: Select, viewer_id: int | None
) -> Select:
    if viewer_id is None:
        return stmt
    hidden = await user_service.blocked_ids(db, viewer_id)
    if hidden:
        stmt = stmt.where(Pulse.author_id.not_in(hidden))
    return stmt


async def get_pulse(
    db: AsyncSession, pulse_id: int, *, allow_deleted: bool = False
) -> Pulse:
    stmt = select(Pulse).options(*_load_options()).where(Pulse.id == pulse_id)
    pulse = await db.scalar(stmt)
    if pulse is None or (pulse.is_deleted and not allow_deleted):
        raise NotFoundError("Pulse not found.")
    return pulse


async def _enforce_rate_limit(db: AsyncSession, author_id: int) -> None:
    since = datetime.now(UTC) - timedelta(hours=1)
    recent = await db.scalar(
        select(func.count())
        .select_from(Pulse)
        .where(Pulse.author_id == author_id, Pulse.created_at >= since)
    )
    if (recent or 0) >= settings.RATE_LIMIT_PULSES_PER_HOUR:
        raise RateLimitedError("You have posted too much in the past hour.")


async def _attach_entities(db: AsyncSession, pulse: Pulse, author: User) -> None:
    """Link hashtags and mentions, and notify the people mentioned."""
    tags = extract_hashtags(pulse.content)
    for tag in tags:
        hashtag = await db.scalar(select(Hashtag).where(Hashtag.tag == tag))
        if hashtag is None:
            hashtag = Hashtag(tag=tag, usage_count=0)
            db.add(hashtag)
            try:
                await db.flush()
            except IntegrityError:
                # Another request created the same tag first.
                await db.rollback()
                hashtag = await db.scalar(select(Hashtag).where(Hashtag.tag == tag))
                if hashtag is None:
                    continue
        hashtag.usage_count += 1
        db.add(PulseHashtag(pulse_id=pulse.id, hashtag_id=hashtag.id))

    usernames = extract_mentions(pulse.content)
    if not usernames:
        return

    mentioned = (
        await db.scalars(
            select(User).where(
                func.lower(User.username).in_(usernames),
                User.is_active.is_(True),
                User.id != author.id,
            )
        )
    ).all()
    for target in mentioned:
        db.add(Mention(pulse_id=pulse.id, user_id=target.id))
        db.add(
            Notification(
                recipient_id=target.id,
                actor_id=author.id,
                type=NotificationType.MENTION,
                pulse_id=pulse.id,
            )
        )


async def create_pulse(db: AsyncSession, author: User, payload: PulseCreate) -> Pulse:
    await _enforce_rate_limit(db, author.id)

    content = normalise_content(payload.content)
    if len(content) > settings.MAX_PULSE_LENGTH:
        raise ValidationError("That pulse is too long.")

    parent: Pulse | None = None
    conversation_id: int | None = None

    if payload.reply_to_id:
        parent = await get_pulse(db, payload.reply_to_id)
        if await user_service.is_blocked_either_way(db, author.id, parent.author_id):
            raise PermissionDeniedError("You cannot reply to this pulse.")
        conversation_id = parent.conversation_id or parent.id

    if payload.quote_of_id:
        parent = await get_pulse(db, payload.quote_of_id)
        if await user_service.is_blocked_either_way(db, author.id, parent.author_id):
            raise PermissionDeniedError("You cannot quote this pulse.")

    media: list[Media] = []
    if payload.media_ids:
        media = list(
            (
                await db.scalars(
                    select(Media).where(
                        Media.id.in_(payload.media_ids),
                        Media.uploader_id == author.id,
                        Media.pulse_id.is_(None),
                    )
                )
            ).all()
        )
        if len(media) != len(set(payload.media_ids)):
            raise ValidationError("One or more images are not available.")

    pulse = Pulse(
        author_id=author.id,
        content=content,
        reply_to_id=payload.reply_to_id,
        quote_of_id=payload.quote_of_id,
    )
    db.add(pulse)
    await db.flush()

    pulse.conversation_id = conversation_id or pulse.id

    order = {mid: i for i, mid in enumerate(payload.media_ids)}
    for item in media:
        item.pulse_id = pulse.id
        item.position = order.get(item.id, 0)

    await db.execute(
        update(User).where(User.id == author.id).values(pulses_count=User.pulses_count + 1)
    )

    if parent is not None and payload.reply_to_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.id == parent.id)
            .values(reply_count=Pulse.reply_count + 1)
        )
        if parent.author_id != author.id:
            db.add(
                Notification(
                    recipient_id=parent.author_id,
                    actor_id=author.id,
                    type=NotificationType.REPLY,
                    pulse_id=pulse.id,
                )
            )
    elif parent is not None and payload.quote_of_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.id == parent.id)
            .values(quote_count=Pulse.quote_count + 1)
        )
        if parent.author_id != author.id:
            db.add(
                Notification(
                    recipient_id=parent.author_id,
                    actor_id=author.id,
                    type=NotificationType.QUOTE,
                    pulse_id=pulse.id,
                )
            )

    await _attach_entities(db, pulse, author)
    await db.commit()
    return await get_pulse(db, pulse.id)


async def delete_pulse(db: AsyncSession, user: User, pulse_id: int) -> None:
    pulse = await get_pulse(db, pulse_id)
    if pulse.author_id != user.id:
        raise PermissionDeniedError("You can only delete your own pulses.")

    pulse.is_deleted = True
    pulse.deleted_at = datetime.now(UTC)

    await db.execute(
        update(User)
        .where(User.id == user.id, User.pulses_count > 0)
        .values(pulses_count=User.pulses_count - 1)
    )
    if pulse.reply_to_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.id == pulse.reply_to_id, Pulse.reply_count > 0)
            .values(reply_count=Pulse.reply_count - 1)
        )
    if pulse.quote_of_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.id == pulse.quote_of_id, Pulse.quote_count > 0)
            .values(quote_count=Pulse.quote_count - 1)
        )
    if pulse.repulse_of_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.id == pulse.repulse_of_id, Pulse.repulse_count > 0)
            .values(repulse_count=Pulse.repulse_count - 1)
        )

    # Reposts carry no content of their own, so once the original is gone they
    # would render as blank cards in every follower's timeline. Retire them
    # with it.
    if not pulse.repulse_of_id:
        await db.execute(
            update(Pulse)
            .where(Pulse.repulse_of_id == pulse.id, Pulse.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=pulse.deleted_at)
        )

    await db.commit()


# --------------------------------------------------------------------------
# Interactions
# --------------------------------------------------------------------------


async def like(db: AsyncSession, user: User, pulse_id: int) -> bool:
    pulse = await get_pulse(db, pulse_id)
    db.add(Like(user_id=user.id, pulse_id=pulse_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    await db.execute(
        update(Pulse).where(Pulse.id == pulse_id).values(like_count=Pulse.like_count + 1)
    )
    if pulse.author_id != user.id:
        db.add(
            Notification(
                recipient_id=pulse.author_id,
                actor_id=user.id,
                type=NotificationType.LIKE,
                pulse_id=pulse_id,
            )
        )
    await db.commit()
    return True


async def unlike(db: AsyncSession, user: User, pulse_id: int) -> bool:
    result = await db.execute(
        delete(Like).where(Like.user_id == user.id, Like.pulse_id == pulse_id)
    )
    if result.rowcount == 0:
        await db.rollback()
        return False
    await db.execute(
        update(Pulse)
        .where(Pulse.id == pulse_id, Pulse.like_count > 0)
        .values(like_count=Pulse.like_count - 1)
    )
    await db.commit()
    return True


async def repulse(db: AsyncSession, user: User, pulse_id: int) -> bool:
    pulse = await get_pulse(db, pulse_id)
    if pulse.repulse_of_id:
        # Reposting a repost boosts the original instead of nesting.
        pulse_id = pulse.repulse_of_id
        pulse = await get_pulse(db, pulse_id)

    db.add(Pulse(author_id=user.id, content="", repulse_of_id=pulse_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    await db.execute(
        update(Pulse)
        .where(Pulse.id == pulse_id)
        .values(repulse_count=Pulse.repulse_count + 1)
    )
    if pulse.author_id != user.id:
        db.add(
            Notification(
                recipient_id=pulse.author_id,
                actor_id=user.id,
                type=NotificationType.REPULSE,
                pulse_id=pulse_id,
            )
        )
    await db.commit()
    return True


async def unrepulse(db: AsyncSession, user: User, pulse_id: int) -> bool:
    result = await db.execute(
        delete(Pulse).where(Pulse.author_id == user.id, Pulse.repulse_of_id == pulse_id)
    )
    if result.rowcount == 0:
        await db.rollback()
        return False
    await db.execute(
        update(Pulse)
        .where(Pulse.id == pulse_id, Pulse.repulse_count > 0)
        .values(repulse_count=Pulse.repulse_count - 1)
    )
    await db.commit()
    return True


async def bookmark(db: AsyncSession, user: User, pulse_id: int) -> bool:
    await get_pulse(db, pulse_id)
    db.add(Bookmark(user_id=user.id, pulse_id=pulse_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    await db.execute(
        update(Pulse)
        .where(Pulse.id == pulse_id)
        .values(bookmark_count=Pulse.bookmark_count + 1)
    )
    await db.commit()
    return True


async def unbookmark(db: AsyncSession, user: User, pulse_id: int) -> bool:
    result = await db.execute(
        delete(Bookmark).where(Bookmark.user_id == user.id, Bookmark.pulse_id == pulse_id)
    )
    if result.rowcount == 0:
        await db.rollback()
        return False
    await db.execute(
        update(Pulse)
        .where(Pulse.id == pulse_id, Pulse.bookmark_count > 0)
        .values(bookmark_count=Pulse.bookmark_count - 1)
    )
    await db.commit()
    return True


async def register_view(db: AsyncSession, pulse_id: int) -> None:
    await db.execute(
        update(Pulse).where(Pulse.id == pulse_id).values(view_count=Pulse.view_count + 1)
    )
    await db.commit()
