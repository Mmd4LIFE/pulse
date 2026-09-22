"""The Pulse Score: what the model made of a pulse, out of ten.

Every pulse with something to read gets one a moment after it is posted. It is
a judgement of the writing -- is it worth someone's attention -- not a
popularity number: likes arrive later and are counted separately, and a score
does not move once it is set.

The model is asked for a single number and nothing else. Anything that does not
come back as one is dropped rather than guessed at: an unscored pulse is a
normal state the interface knows how to show.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Pulse, PulseScore, ScoreSource
from app.services import ai

log = get_logger(__name__)

LOWEST = Decimal("0.0")
HIGHEST = Decimal("10.0")
STEP = Decimal("0.1")

SYSTEM = """You rate short social posts for Pulse, a Twitter-like feed.

Give one score from 0.0 to 10.0 with exactly one decimal place, like an IMDb \
rating. Judge the post as writing: is it worth a stranger's attention? Weigh \
clarity, originality, wit, and whether it says something. Ignore who wrote it, \
how popular it is, and what language it is in -- a good post in Persian or \
Arabic scores exactly as it would in English.

Use the whole range and be discerning. Most ordinary posts land between 4.0 \
and 7.0. Reserve 9.0 and above for writing that genuinely stands out, and 2.0 \
and below for the empty or incoherent. Avoid whole numbers where a finer one \
fits.

Reply with the number alone. No words, no punctuation, no explanation."""

# The model is told to answer with a bare number; this also survives a stray
# "Score: 7.8" or a trailing full stop, which is cheaper than a retry. The
# lookarounds are what stop "100" from being read as ten and "-3" as three:
# a number has to stand on its own to count as an answer.
NUMBER_RE = re.compile(r"(?<![\d.\-])(\d{1,2}(?:\.\d+)?)(?!\d)")


def is_enabled() -> bool:
    return bool(settings.SCORE_ENABLED and settings.OPENAI_API_KEY)


def parse(text: str) -> Decimal | None:
    """Read a score out of the model's reply, or None if there isn't one."""
    match = NUMBER_RE.search(text)
    if match is None:
        return None
    try:
        value = Decimal(match.group(1))
    except InvalidOperation:
        return None
    if not (LOWEST <= value <= HIGHEST):
        return None
    return value.quantize(STEP)


def is_scorable(pulse: Pulse) -> bool:
    """Reposts carry no words of their own, and deleted pulses are not read."""
    if pulse.is_deleted or pulse.repulse_of_id is not None:
        return False
    return bool(pulse.content.strip())


async def scored_today(db: AsyncSession) -> int:
    """How many scores the model has given since midnight UTC."""
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await db.scalar(
            select(func.count())
            .select_from(PulseScore)
            .where(
                PulseScore.source == ScoreSource.AI,
                PulseScore.created_at >= since,
            )
        )
    ) or 0


async def for_pulses(db: AsyncSession, pulse_ids: Sequence[int]) -> dict[int, Decimal]:
    """The model's score for each of these pulses, for the ones that have one.

    One query for a whole page, the way the viewer-relative flags are read.
    """
    if not pulse_ids:
        return {}
    rows = await db.execute(
        select(PulseScore.pulse_id, PulseScore.value).where(
            PulseScore.pulse_id.in_(set(pulse_ids)),
            PulseScore.source == ScoreSource.AI,
        )
    )
    return dict(rows.all())


async def existing(db: AsyncSession, pulse_id: int) -> Decimal | None:
    return await db.scalar(
        select(PulseScore.value).where(
            PulseScore.pulse_id == pulse_id, PulseScore.source == ScoreSource.AI
        )
    )


async def score_pulse(db: AsyncSession, pulse_id: int) -> Decimal | None:
    """Score one pulse and store it. Returns None when it was not scored."""
    if not is_enabled():
        return None

    pulse = await db.get(Pulse, pulse_id)
    if pulse is None or not is_scorable(pulse):
        return None

    already = await existing(db, pulse_id)
    if already is not None:
        return already

    used = await scored_today(db)
    if used >= settings.SCORE_MAX_PER_DAY:
        log.info("score_budget_spent", used=used)
        return None

    try:
        completion = await ai.complete(
            SYSTEM,
            pulse.content,
            max_tokens=8,
            # A score should be the same answer twice, so nothing is left to
            # chance that does not have to be.
            temperature=0.2,
        )
    except ai.AiError as exc:
        log.info("score_failed", pulse_id=pulse_id, error=str(exc))
        return None

    score = parse(completion.text)
    if score is None:
        log.info("score_unreadable", pulse_id=pulse_id, reply=completion.text[:40])
        return None

    db.add(
        PulseScore(
            pulse_id=pulse_id,
            source=ScoreSource.AI,
            value=score,
            model=settings.OPENAI_MODEL,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        # Two scorings raced -- posting twice in a moment, say. The one that
        # landed is as good as this one, so keep it rather than overwrite it.
        await db.rollback()
        return await existing(db, pulse_id)

    log.info("score_set", pulse_id=pulse_id, score=str(score), tokens=completion.tokens)
    return score


async def score_in_background(pulse_id: int) -> None:
    """Entry point for FastAPI's background tasks.

    The request's session is closed by the time this runs, so it opens its own.
    Nothing here may raise: a pulse that could not be scored is still posted.
    """
    from app.db.session import SessionLocal

    try:
        async with SessionLocal() as session:
            await score_pulse(session, pulse_id)
    except Exception as exc:
        log.warning("score_crashed", pulse_id=pulse_id, error=str(exc))
