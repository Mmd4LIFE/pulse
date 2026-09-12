"""Automated accounts: creating them, and giving them something to do.

Everything here goes through the ordinary service layer -- ``create_pulse``,
``like``, ``repulse``, ``follow``. That is the point. Rate limits, counters,
notifications, blocks and protected accounts all apply to these accounts
because nothing was written to bypass them, and a change to any of those rules
covers automated accounts for free.
"""

from __future__ import annotations

import random
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models import Persona, Pulse, User
from app.schemas.pulse import PulseCreate
from app.services import ai
from app.services import pulses as pulse_service
from app.services import users as user_service

log = get_logger(__name__)

MAX_PULSE = settings.MAX_PULSE_LENGTH

LANGUAGE_NAMES = {
    "en": "English",
    "fa": "Persian (Farsi)",
    "ar": "Arabic",
    "tr": "Turkish",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------


async def reattach(db: AsyncSession, persona: Persona) -> Persona:
    """Reload a persona whose state a rollback may have expired.

    ``like`` and ``repulse`` roll back when the edge already exists, and a
    rollback expires every object in the session -- including ones belonging to
    a different account's turn later in the same batch. The prompt is built
    from ``persona.user``, so reading it afterwards triggers a lazy load in a
    context that cannot perform IO, which SQLAlchemy reports as
    "greenlet_spawn has not been called".

    Reloading is cheap next to a model call, and makes every entry point here
    safe to call whatever happened before it.
    """
    # Read the primary key from the mapper's identity rather than from the
    # attribute. After a rollback ``persona.id`` is expired too, so touching it
    # to build the query would trip the very lazy load this exists to avoid.
    identity = inspect(persona).identity
    if identity is None:
        return persona  # never persisted; nothing to reload

    reloaded = await db.scalar(select(Persona).where(Persona.id == identity[0]))
    return reloaded if reloaded is not None else persona


def _house_rules(persona: Persona) -> str:
    """The constraints every generation shares, whatever it is being asked for."""
    return (
        f"You are {persona.user.display_name} (@{persona.user.username}), a member of "
        f"a small social feed called Pulse.\n\n"
        f"Who you are: {persona.character}\n"
        f"What you post about: {persona.topic}\n"
        f"You write in {language_name(persona.language)}.\n\n"
        "How you write:\n"
        f"- At most {MAX_PULSE} characters. Usually far fewer. One thought, not an essay.\n"
        "- Like a person typing quickly, not like marketing copy or a press release.\n"
        "- Be specific. Mention the actual thing, not the category it belongs to.\n"
        "- Most posts should carry no hashtag at all. One, rarely, and only when it "
        "is a tag people actually follow. Never tack one on to summarise the post.\n"
        "- No emoji unless it is truly how you would write.\n"
        "- Vary the length. Some thoughts are one line. Not everything needs a "
        "conclusion sentence.\n"
        "- Never mention being an AI, a model, a bot, or that you were prompted.\n"
        "- Never claim to be a real, named public figure, and never speak for a "
        "real company or organisation as if you worked there.\n"
        "- Nothing hateful, harassing, sexual, or medically or financially "
        "prescriptive.\n\n"
        "Reply with the post text and nothing else. No quotation marks, no preamble, "
        "no label."
    )


def clean_generated(text: str) -> str:
    """Strip the wrappers models like to add, and fit it to a pulse."""
    cleaned = text.strip()

    # Models often wrap a one-line answer in quotes, or prefix it with a label.
    cleaned = re.sub(r"^(post|reply|tweet|pulse)\s*[:\-]\s*", "", cleaned, flags=re.I)
    if len(cleaned) >= 2 and cleaned[0] in "\"'“«" and cleaned[-1] in "\"'”»":
        cleaned = cleaned[1:-1].strip()

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned) <= MAX_PULSE:
        return cleaned
    # Prefer to end on a sentence, then a word, rather than mid-syllable.
    window = cleaned[:MAX_PULSE]
    for boundary in (". ", "! ", "? ", "؟ ", "، ", ", ", " "):
        cut = window.rfind(boundary)
        if cut > MAX_PULSE * 0.6:
            return window[: cut + len(boundary)].strip()
    return window.strip()


# ---------------------------------------------------------------------------
# Creating an account
# ---------------------------------------------------------------------------

_HANDLE_RE = re.compile(r"[^a-z0-9_]")


async def _unique_handle(db: AsyncSession, suggestion: str) -> str:
    base = _HANDLE_RE.sub("", suggestion.lower().strip().replace(" ", "_"))[:24]
    if len(base) < 3:
        base = f"user{secrets.randbelow(9000) + 1000}"

    for candidate in (base, *(f"{base}{n}" for n in range(1, 60))):
        taken = await db.scalar(
            select(User.id).where(func.lower(User.username) == candidate.lower())
        )
        if taken is None:
            return candidate
    return f"{base[:20]}{secrets.randbelow(9000) + 1000}"


async def invent_identity(topic: str, language: str) -> dict[str, str]:
    """Ask the model for a person to be, given a subject."""
    system = (
        "You invent believable members of a small social feed. Return exactly four "
        "lines, each 'field: value', with no other text:\n"
        "name: a plausible full name for a real person\n"
        "handle: lowercase letters, digits and underscores, 3-20 characters\n"
        "bio: under 140 characters, first person, specific, no hashtags\n"
        "character: two or three sentences describing how this person thinks and "
        "writes -- their habits, what they notice, what irritates them. Written as "
        "instructions to whoever plays them.\n\n"
        "The person must be fictional. Do not use the name of a real public figure."
    )
    user = (
        f"Subject they post about: {topic}\n"
        f"They write in {language_name(language)}. "
        "The name and bio should suit someone who writes in that language."
    )

    result = await ai.complete(system, user, max_tokens=320, temperature=1.0)

    fields: dict[str, str] = {}
    for line in result.text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in {"name", "handle", "bio", "character"}:
            fields[key] = value.strip().strip('"')

    if not fields.get("character"):
        raise ai.AiError("the model did not describe a character")

    fields.setdefault("name", topic.title()[:64])
    fields.setdefault("handle", "")
    fields.setdefault("bio", "")
    return fields


async def create_persona(
    db: AsyncSession,
    *,
    topic: str,
    language: str = "en",
    post_every_minutes: int = 180,
    reply_chance: float = 0.25,
    like_chance: float = 0.5,
    repulse_chance: float = 0.08,
) -> Persona:
    """Invent an account for a subject and bring it into being."""
    identity = await invent_identity(topic, language)

    # Telegram ids are positive; automated accounts take negative ones so they
    # can never collide with a real sign-in.
    telegram_id = -abs(secrets.randbits(40)) - 1

    user = User(
        telegram_id=telegram_id,
        username=await _unique_handle(db, identity["handle"] or identity["name"]),
        display_name=identity["name"][:64],
        bio=(identity["bio"] or None),
        language_code=language[:8],
        is_automated=True,
    )
    db.add(user)
    await db.flush()

    persona = Persona(
        user_id=user.id,
        topic=topic[:120],
        character=identity["character"],
        language=language[:8],
        post_every_minutes=max(5, post_every_minutes),
        reply_chance=min(max(reply_chance, 0.0), 1.0),
        like_chance=min(max(like_chance, 0.0), 1.0),
        repulse_chance=min(max(repulse_chance, 0.0), 1.0),
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    log.info(
        "persona_created",
        user_id=user.id,
        username=user.username,
        topic=topic,
        language=language,
    )
    return persona


# A spread of subjects for seeding a population. A feed where two hundred
# accounts all discuss one thing reads as a bot farm; a feed with this many
# separate conversations reads as a place.
TOPIC_POOL: list[tuple[str, str]] = [
    # --- Persian ---------------------------------------------------------
    ("fa", "برنامه‌نویسی وب و تجربه‌ی کار با فریم‌ورک‌های جاوااسکریپت"),
    ("fa", "طراحی رابط کاربری و تایپوگرافی فارسی"),
    ("fa", "استارتاپ‌های ایرانی، جذب کاربر و درس‌هایی که گرفته‌اند"),
    ("fa", "عکاسی خیابانی در شهرهای ایران"),
    ("fa", "ادبیات فارسی، شعر معاصر و کتاب‌هایی که تازه خوانده"),
    ("fa", "آشپزی خانگی و غذاهای محلی ایران"),
    ("fa", "کوهنوردی و طبیعت‌گردی در البرز و زاگرس"),
    ("fa", "موسیقی سنتی و ساز نواختن"),
    ("fa", "خودرو، موتورسیکلت و تعمیرات دست‌ساز"),
    ("fa", "معماری شهری و فضاهای عمومی تهران"),
    ("fa", "بازی‌های ویدیویی و صنعت گیم در ایران"),
    ("fa", "زندگی دانشجویی، کنکور و انتخاب رشته"),
    ("fa", "سلامت، ورزش روزمره و دویدن"),
    ("fa", "فیلم و سریال، نقد و معرفی"),
    ("fa", "کارآفرینی کوچک، فروشگاه آنلاین و بسته‌بندی"),
    # --- English ---------------------------------------------------------
    ("en", "backend engineering, Postgres and shipping side projects"),
    ("en", "frontend performance and the browser's rendering path"),
    ("en", "type design, kerning and the history of letterforms"),
    ("en", "film photography and darkroom printing"),
    ("en", "long-distance running and training plans that went wrong"),
    ("en", "home cooking, fermentation and cheap ingredients"),
    ("en", "indie game development and the things nobody warns you about"),
    ("en", "urban cycling, commuting and bike maintenance"),
    ("en", "self-hosting, home servers and small networks"),
    ("en", "books, mostly non-fiction, and arguing about them"),
    ("en", "electronic music production in a very small room"),
    ("en", "woodworking with hand tools"),
    ("en", "climate, energy policy and the numbers behind both"),
    ("en", "birdwatching and what turns up in a city park"),
    ("en", "designing and printing board games"),
    ("en", "mechanical keyboards and the sound of switches"),
    ("en", "teaching yourself mathematics as an adult"),
    ("en", "gardening on a balcony"),
    ("en", "old cars, carburettors and weekends lost to them"),
    ("en", "coffee, roasting at home and being insufferable about it"),
]


# ---------------------------------------------------------------------------
# Acting
# ---------------------------------------------------------------------------


async def generations_today(db: AsyncSession) -> int:
    """Posts and replies made by automated accounts since midnight UTC."""
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    automated = select(User.id).where(User.is_automated.is_(True))
    return (
        await db.scalar(
            select(func.count())
            .select_from(Pulse)
            .where(Pulse.author_id.in_(automated), Pulse.created_at >= since)
        )
    ) or 0


async def _posts_today(db: AsyncSession, persona: Persona) -> int:
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await db.scalar(
            select(func.count())
            .select_from(Pulse)
            .where(Pulse.author_id == persona.user_id, Pulse.created_at >= since)
        )
    ) or 0


def is_due_to_post(persona: Persona, *, now: datetime | None = None) -> bool:
    """Whether enough time has passed, with some slack so accounts desynchronise."""
    now = now or datetime.now(UTC)
    if persona.last_posted_at is None:
        return True
    # +/- 30% jitter, so accounts created together drift apart instead of
    # posting in a block every time.
    spacing = persona.post_every_minutes * random.uniform(0.7, 1.3)
    return now - persona.last_posted_at >= timedelta(minutes=spacing)


async def write_post(db: AsyncSession, persona: Persona) -> Pulse | None:
    """Generate and publish one post."""
    persona = await reattach(db, persona)
    recent = (
        await db.scalars(
            select(Pulse.content)
            .where(
                Pulse.author_id == persona.user_id,
                Pulse.is_deleted.is_(False),
                Pulse.reply_to_id.is_(None),
            )
            .order_by(Pulse.id.desc())
            .limit(6)
        )
    ).all()

    avoid = ""
    if recent:
        joined = "\n".join(f"- {c}" for c in recent if c)
        avoid = (
            "\n\nYou have recently posted the following. Do not repeat these points, "
            f"and do not open the same way:\n{joined}"
        )

    result = await ai.complete(
        _house_rules(persona),
        "Write your next post. Something you have noticed or been thinking about "
        f"lately, in your own voice.{avoid}",
    )
    content = clean_generated(result.text)
    if not content:
        return None

    pulse = await pulse_service.create_pulse(db, persona.user, PulseCreate(content=content))

    persona.last_posted_at = datetime.now(UTC)
    persona.posts_made += 1
    persona.tokens_used += result.tokens
    await db.commit()
    return pulse


async def write_reply(db: AsyncSession, persona: Persona, target: Pulse) -> Pulse | None:
    """Generate and publish a reply to someone else's pulse."""
    persona = await reattach(db, persona)

    # Without this, two accounts answering the same pulse independently arrive
    # at almost the same sentence -- which is exactly what gives automation
    # away. Showing the thread lets each one say something the others did not.
    existing = (
        await db.scalars(
            select(Pulse)
            .where(
                Pulse.reply_to_id == target.id,
                Pulse.is_deleted.is_(False),
                Pulse.author_id != persona.user_id,
            )
            .order_by(Pulse.id.desc())
            .limit(5)
        )
    ).all()

    said = ""
    if existing:
        joined = "\n".join(f"- {r.content}" for r in existing if r.content)
        said = (
            "\n\nOthers have already replied with the following. Do not repeat any "
            "of these points, do not agree in the same words, and do not open the "
            f"same way. Say something they have not:\n{joined}"
        )

    result = await ai.complete(
        _house_rules(persona),
        "Someone on your feed posted this:\n\n"
        f"@{target.author.username}: {target.content}\n\n"
        "Reply to them. Address what they actually said -- agree, disagree, add "
        "something, or ask. Keep it short, the way a reply is. Do not restate "
        f"their point back at them, and do not start with their name.{said}",
        max_tokens=160,
    )
    content = clean_generated(result.text)
    if not content:
        return None

    reply = await pulse_service.create_pulse(
        db, persona.user, PulseCreate(content=content, reply_to_id=target.id)
    )

    persona.replies_made += 1
    persona.tokens_used += result.tokens
    persona.last_acted_at = datetime.now(UTC)
    await db.commit()
    return reply


async def candidates_to_engage(
    db: AsyncSession, persona: Persona, limit: int = 25
) -> list[Pulse]:
    """Recent pulses this account might react to.

    Excludes its own, and anything it has already replied to. Automated
    accounts are not excluded -- a feed where they ignore each other reads as
    oddly as one where they only talk to each other -- but the reply chance is
    what keeps that from turning into a loop.
    """
    since = datetime.now(UTC) - timedelta(hours=settings.AI_TIMELINE_LOOKBACK_HOURS)
    already = select(Pulse.reply_to_id).where(
        Pulse.author_id == persona.user_id, Pulse.reply_to_id.is_not(None)
    )

    rows = await db.scalars(
        select(Pulse)
        .where(
            Pulse.is_deleted.is_(False),
            Pulse.author_id != persona.user_id,
            Pulse.repulse_of_id.is_(None),
            Pulse.created_at >= since,
            Pulse.id.not_in(already),
            # A reply to a reply to a reply goes nowhere interesting.
            Pulse.reply_to_id.is_(None),
        )
        .order_by(Pulse.id.desc())
        .limit(limit)
    )
    return list(rows.unique().all())


async def act(db: AsyncSession, persona: Persona) -> dict[str, int]:
    """One turn for one account: perhaps post, perhaps engage.

    Returns what it did, for the worker to log. Failures are recorded on the
    persona and swallowed, so one broken account cannot stop the rest.
    """
    did = {"posted": 0, "replied": 0, "liked": 0, "repulsed": 0}

    # A previous account's turn in this batch may have rolled back, expiring
    # everything in the session including this object.
    persona = await reattach(db, persona)

    # Marked up front. The worker takes accounts least-recently-acted first, so
    # one that has its turn and does nothing must still count as having had it;
    # otherwise it is picked first again next tick and the rest never come
    # round.
    persona.last_acted_at = datetime.now(UTC)

    try:
        under_daily_cap = (
            await _posts_today(db, persona) < settings.AI_MAX_POSTS_PER_ACCOUNT_PER_DAY
        )
        if (
            is_due_to_post(persona)
            and under_daily_cap
            and await write_post(db, persona) is not None
        ):
            did["posted"] = 1

        candidates = await candidates_to_engage(db, persona)
        if candidates:
            # Weighted towards the newest, but not exclusively, so older pulses
            # still pick up the occasional response.
            target = random.choice(candidates[:8] or candidates)

            if random.random() < persona.like_chance and await pulse_service.like(
                db, persona.user, target.id
            ):
                did["liked"] = 1

            if random.random() < persona.repulse_chance and await pulse_service.repulse(
                db, persona.user, target.id
            ):
                did["repulsed"] = 1

            if (
                random.random() < persona.reply_chance
                and target.content
                and await write_reply(db, persona, target) is not None
            ):
                did["replied"] = 1

        # The engagement steps roll back on a duplicate; reload before the
        # bookkeeping below touches this object again.
        persona = await reattach(db, persona)
        persona.last_acted_at = datetime.now(UTC)
        persona.last_error = None
        await db.commit()

    except ai.AiError as exc:
        await db.rollback()
        persona.last_error = str(exc)[:255]
        await db.commit()
        log.warning("persona_generation_failed", user_id=persona.user_id, reason=str(exc))
    except AppError as exc:
        # A domain rule said no -- rate limited, blocked, protected. Expected.
        await db.rollback()
        log.info("persona_action_refused", user_id=persona.user_id, reason=str(exc))
    except Exception as exc:
        await db.rollback()
        persona.last_error = str(exc)[:255]
        await db.commit()
        log.exception("persona_act_failed", user_id=persona.user_id, error=str(exc))

    return did


async def follow_each_other(db: AsyncSession, persona: Persona, sample: int = 4) -> int:
    """Give a new account a handful of people to follow, so its feed is not empty."""
    others = (
        await db.scalars(
            select(User)
            .where(User.id != persona.user_id, User.is_active.is_(True))
            .order_by(func.random())
            .limit(sample)
        )
    ).all()

    followed = 0
    for other in others:
        try:
            if await user_service.follow(db, persona.user, other.id) in {
                "following",
                "requested",
            }:
                followed += 1
        except AppError:
            continue
    return followed


async def wire_follows(db: AsyncSession, per_account: int = 8) -> int:
    """Give a freshly seeded population a follow graph.

    Each account follows a few others, weighted towards ones on its own subject
    so the graph has communities in it rather than being uniform noise, with a
    couple of cross-subject edges so the clusters are joined.
    """
    personas = list(
        (await db.scalars(select(Persona).where(Persona.is_active.is_(True))))
        .unique()
        .all()
    )
    if len(personas) < 2:
        return 0

    by_topic: dict[str, list[Persona]] = {}
    for persona in personas:
        by_topic.setdefault(persona.topic, []).append(persona)

    edges = 0
    for index, persona in enumerate(personas, start=1):
        neighbours = [p for p in by_topic[persona.topic] if p.id != persona.id]
        strangers = [p for p in personas if p.topic != persona.topic]

        # Mostly people talking about the same thing, plus a couple from
        # elsewhere -- roughly how anyone's following list looks.
        same = random.sample(neighbours, min(len(neighbours), max(1, per_account - 2)))
        other = random.sample(strangers, min(len(strangers), 2))

        for target in (*same, *other):
            if await follow_quietly(db, persona.user_id, target.user_id):
                edges += 1

        # Committed in batches so a long run does not build one enormous
        # transaction.
        if index % 25 == 0:
            await db.commit()

    await db.commit()
    return edges


async def follow_quietly(db: AsyncSession, follower_id: int, followee_id: int) -> bool:
    """Add a follow edge without a notification.

    Seeding a population creates thousands of edges at once. Routing those
    through the ordinary follow would fill every inbox with a wall of them
    before anyone had seen a single post.

    Uses ON CONFLICT rather than catching the duplicate: a caught IntegrityError
    has to be rolled back, and a rollback here would discard every edge added
    since the last commit, not just the one that clashed.
    """
    from sqlalchemy import update
    from sqlalchemy.dialects.postgresql import insert

    from app.models import Follow

    if follower_id == followee_id:
        return False

    result = await db.execute(
        insert(Follow)
        .values(follower_id=follower_id, followee_id=followee_id)
        .on_conflict_do_nothing(index_elements=["follower_id", "followee_id"])
    )
    if not result.rowcount:
        return False

    await db.execute(
        update(User)
        .where(User.id == follower_id)
        .values(following_count=User.following_count + 1)
    )
    await db.execute(
        update(User)
        .where(User.id == followee_id)
        .values(followers_count=User.followers_count + 1)
    )
    return True
