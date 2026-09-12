"""Automated accounts: how they are made, and how they behave."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services import ai
from app.services import personas as ps


class FakeModel:
    """Stands in for the completions API, recording what it was asked."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, system, user, **kwargs):
        self.calls.append((system, user))
        text = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return ai.Completion(text=text, tokens=42)


IDENTITY = (
    "name: Nazanin Farahani\n"
    "handle: nazanin_type\n"
    "bio: Type designer in Isfahan. I care about the space between letters.\n"
    "character: Notices kerning everywhere and cannot let it go. Writes in short, "
    "dry observations and rarely explains herself."
)


@pytest.fixture
def model(monkeypatch):
    """Install a fake model and pretend generation is switched on."""

    def install(*replies: str) -> FakeModel:
        fake = FakeModel(*replies)
        monkeypatch.setattr(ps.ai, "complete", fake)
        monkeypatch.setattr(ps.ai, "is_configured", lambda: True)
        return fake

    return install


# --- cleaning what the model returns ---------------------------------------


def test_surrounding_quotes_are_stripped() -> None:
    assert ps.clean_generated('"Kerning is not spacing."') == "Kerning is not spacing."
    assert ps.clean_generated("“دو حرف، یک فاصله”") == "دو حرف، یک فاصله"


def test_a_label_prefix_is_stripped() -> None:
    assert ps.clean_generated("Post: shipped it") == "shipped it"
    assert ps.clean_generated("Reply - fair point") == "fair point"


def test_an_overlong_answer_is_cut_on_a_sentence() -> None:
    text = ("This is a complete sentence. " * 20).strip()
    cleaned = ps.clean_generated(text)
    assert len(cleaned) <= 280
    assert cleaned.endswith(".")


def test_a_single_long_run_is_still_cut_to_the_limit() -> None:
    cleaned = ps.clean_generated("x" * 500)
    assert len(cleaned) == 280


def test_persian_is_not_mangled() -> None:
    text = "کرنینگ مثل تنظیم فاصله بین حروف است، بدون آن جمله‌ها زیبا نمی‌شوند."
    assert ps.clean_generated(text) == text


# --- cadence ---------------------------------------------------------------


def test_an_account_that_has_never_posted_is_due() -> None:
    persona = ps.Persona(post_every_minutes=180, last_posted_at=None)
    assert ps.is_due_to_post(persona) is True


def test_an_account_that_just_posted_is_not_due() -> None:
    persona = ps.Persona(
        post_every_minutes=180, last_posted_at=datetime.now(UTC) - timedelta(minutes=5)
    )
    assert ps.is_due_to_post(persona) is False


def test_cadence_is_jittered_so_accounts_do_not_post_in_lockstep() -> None:
    """Two accounts on the same schedule must not fire on the same tick forever."""
    now = datetime.now(UTC)
    persona = ps.Persona(
        post_every_minutes=100, last_posted_at=now - timedelta(minutes=100)
    )
    verdicts = {ps.is_due_to_post(persona, now=now) for _ in range(200)}
    assert verdicts == {True, False}, "the interval is not being jittered"


# --- creating --------------------------------------------------------------


async def test_creating_an_account_gives_it_a_person(db, model, client) -> None:
    fake = model(IDENTITY)
    persona = await ps.create_persona(db, topic="type design", language="fa")

    assert persona.user.display_name == "Nazanin Farahani"
    assert persona.user.username == "nazanin_type"
    assert "Isfahan" in (persona.user.bio or "")
    assert "kerning" in persona.character.lower()
    assert persona.language == "fa"
    assert "Persian" in fake.calls[0][1]

    # It reads as an ordinary account from outside.
    profile = (await client.get("/api/v1/users/nazanin_type")).json()
    assert profile["display_name"] == "Nazanin Farahani"
    assert "is_automated" not in profile


async def test_the_operator_can_still_tell_it_apart(db, model) -> None:
    """Invisible in the API, but never invisible to whoever runs the deployment."""
    model(IDENTITY)
    persona = await ps.create_persona(db, topic="type design")
    assert persona.user.is_automated is True


async def test_a_taken_handle_does_not_collide(db, model, make_user) -> None:
    await make_user("nazanin_type")
    model(IDENTITY)
    persona = await ps.create_persona(db, topic="type design")
    assert persona.user.username != "nazanin_type"
    assert persona.user.username.startswith("nazanin_type")


async def test_automated_accounts_cannot_collide_with_a_real_sign_in(db, model) -> None:
    """Telegram ids are positive, so these take negative ones."""
    model(IDENTITY)
    persona = await ps.create_persona(db, topic="type design")
    assert persona.user.telegram_id < 0


async def test_a_model_that_returns_nothing_usable_fails_loudly(db, monkeypatch) -> None:
    async def useless(system, user, **kwargs):
        return ai.Completion(text="I'm sorry, I can't help with that.", tokens=5)

    monkeypatch.setattr(ps.ai, "complete", useless)
    monkeypatch.setattr(ps.ai, "is_configured", lambda: True)

    with pytest.raises(ai.AiError):
        await ps.create_persona(db, topic="type design")


# --- posting and engaging --------------------------------------------------


async def test_an_account_posts_in_its_own_voice(db, model, client) -> None:
    model(IDENTITY, "Kerning is not spacing, and the difference shows at 8pt.")
    persona = await ps.create_persona(db, topic="type design")

    pulse = await ps.write_post(db, persona)
    assert pulse is not None
    assert pulse.content.startswith("Kerning is not spacing")
    assert persona.posts_made == 1
    assert persona.tokens_used > 0

    explore = (await client.get("/api/v1/feed/explore")).json()
    assert [p["content"] for p in explore["items"]] == [pulse.content]


async def test_it_is_told_what_it_already_said(db, model) -> None:
    """Otherwise an account circles the same two opinions forever."""
    fake = model(IDENTITY, "First thought about metrics.")
    persona = await ps.create_persona(db, topic="type design")
    await ps.write_post(db, persona)

    fake.calls.clear()
    await ps.write_post(db, persona)
    assert "First thought about metrics." in fake.calls[0][1]


async def test_it_replies_to_what_was_actually_said(
    db, model, make_user, as_user, client
) -> None:
    human = await make_user("human")
    posted = await client.post(
        "/api/v1/pulses",
        json={"content": "Variable fonts finally feel usable in the browser."},
        headers=as_user(human),
    )
    target_id = posted.json()["id"]

    fake = model(IDENTITY, "Depends on the axes. Optical size is the one that matters.")
    persona = await ps.create_persona(db, topic="type design")

    from sqlalchemy import select

    from app.models import Pulse

    target = await db.scalar(select(Pulse).where(Pulse.id == target_id))
    reply = await ps.write_reply(db, persona, target)

    assert reply is not None and reply.reply_to_id == target_id
    assert "Variable fonts finally feel usable" in fake.calls[-1][1]

    # It behaves like any other reply: the thread and the notification are real.
    thread = (await client.get(f"/api/v1/pulses/{target_id}/thread")).json()
    assert [r["id"] for r in thread["replies"]] == [reply.id]
    inbox = (await client.get("/api/v1/notifications", headers=as_user(human))).json()
    assert [n["type"] for n in inbox["items"]] == ["reply"]


async def test_it_does_not_reply_to_the_same_pulse_twice(
    db, model, make_user, as_user, client
) -> None:
    human = await make_user("human")
    await client.post(
        "/api/v1/pulses", json={"content": "One post"}, headers=as_user(human)
    )

    model(IDENTITY, "A reply")
    persona = await ps.create_persona(db, topic="type design")

    first = await ps.candidates_to_engage(db, persona)
    assert len(first) == 1
    await ps.write_reply(db, persona, first[0])

    assert await ps.candidates_to_engage(db, persona) == []


async def test_it_never_engages_with_itself(db, model) -> None:
    model(IDENTITY, "Something I noticed")
    persona = await ps.create_persona(db, topic="type design")
    await ps.write_post(db, persona)

    assert await ps.candidates_to_engage(db, persona) == []


async def test_a_turn_can_post_like_and_reply(
    db, model, make_user, as_user, client
) -> None:
    human = await make_user("human")
    await client.post(
        "/api/v1/pulses", json={"content": "Something to react to"}, headers=as_user(human)
    )

    model(IDENTITY, "Generated text")
    persona = await ps.create_persona(db, topic="type design")
    # Remove the dice: this is about the actions, not the probabilities.
    persona.like_chance = 1.0
    persona.reply_chance = 1.0
    persona.repulse_chance = 1.0

    did = await ps.act(db, persona)
    assert did == {"posted": 1, "replied": 1, "liked": 1, "repulsed": 1}

    thread = (await client.get("/api/v1/users/human/pulses")).json()
    assert thread["items"][0]["like_count"] == 1
    assert thread["items"][0]["repulse_count"] == 1
    assert thread["items"][0]["reply_count"] == 1


async def test_a_quiet_account_does_nothing(db, model, make_user, as_user, client) -> None:
    human = await make_user("human")
    await client.post("/api/v1/pulses", json={"content": "Ignored"}, headers=as_user(human))

    model(IDENTITY, "Generated text")
    persona = await ps.create_persona(db, topic="type design")
    persona.like_chance = persona.reply_chance = persona.repulse_chance = 0.0
    persona.last_posted_at = datetime.now(UTC)

    assert await ps.act(db, persona) == {
        "posted": 0,
        "replied": 0,
        "liked": 0,
        "repulsed": 0,
    }


async def test_the_daily_cap_stops_an_account_posting(db, model, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_MAX_POSTS_PER_ACCOUNT_PER_DAY", 1)

    model(IDENTITY, "A post")
    persona = await ps.create_persona(db, topic="type design")
    persona.like_chance = persona.reply_chance = persona.repulse_chance = 0.0

    assert (await ps.act(db, persona))["posted"] == 1
    persona.last_posted_at = None  # due again, but over the cap
    assert (await ps.act(db, persona))["posted"] == 0


async def test_a_generation_failure_is_recorded_not_raised(db, model, monkeypatch) -> None:
    model(IDENTITY)
    persona = await ps.create_persona(db, topic="type design")

    async def failing(system, user, **kwargs):
        raise ai.AiError("provider is down", retryable=True)

    monkeypatch.setattr(ps.ai, "complete", failing)
    did = await ps.act(db, persona)

    assert did["posted"] == 0
    assert persona.last_error is not None and "down" in persona.last_error


async def test_they_obey_the_same_rules_as_anyone_else(
    db, model, make_user, as_user, client
) -> None:
    """A protected account is invisible to them, because nothing exempts them."""
    owner = await make_user("owner")
    await client.post("/api/v1/pulses", json={"content": "Private"}, headers=as_user(owner))
    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )

    model(IDENTITY, "Generated")
    persona = await ps.create_persona(db, topic="type design")

    # candidates_to_engage is not privacy-aware on its own, but the act of
    # replying goes through the same service a person uses, which is.
    from sqlalchemy import select

    from app.core.errors import PermissionDeniedError
    from app.models import Pulse

    target = await db.scalar(select(Pulse).where(Pulse.author_id == owner.id))
    from app.services import users as user_service

    await user_service.block(db, owner, persona.user_id)
    with pytest.raises(PermissionDeniedError):
        await ps.write_reply(db, persona, target)


async def test_nothing_is_generated_while_the_feature_is_off(db, monkeypatch) -> None:
    monkeypatch.setattr(ps.ai, "is_configured", lambda: False)
    with pytest.raises(ai.AiDisabledError):
        await ai.complete("system", "user")


async def test_it_is_shown_the_replies_already_on_a_pulse(
    db, model, make_user, as_user, client
) -> None:
    """Two accounts answering the same pulse must not arrive at one sentence."""
    human = await make_user("human")
    posted = await client.post(
        "/api/v1/pulses",
        json={"content": "Spacing matters more than letterforms."},
        headers=as_user(human),
    )
    target_id = posted.json()["id"]

    first = await make_user("early_bird")
    await client.post(
        "/api/v1/pulses",
        json={"content": "Agreed, rhythm beats shape.", "reply_to_id": target_id},
        headers=as_user(first),
    )

    fake = model(IDENTITY, "Depends on the size you set it at.")
    persona = await ps.create_persona(db, topic="type design")

    from sqlalchemy import select

    from app.models import Pulse

    target = await db.scalar(select(Pulse).where(Pulse.id == target_id))
    await ps.write_reply(db, persona, target)

    prompt = fake.calls[-1][1]
    assert "Agreed, rhythm beats shape." in prompt
    assert "Do not repeat any of these points" in prompt
