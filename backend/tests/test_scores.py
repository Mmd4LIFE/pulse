"""The Pulse Score.

The model is stubbed. What is tested here is everything around it: what gets
scored at all, that a score is read back with the pulse, that the day's
spending is bounded, and that a score is not given twice.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Pulse, PulseScore, ScoreSource
from app.services import ai
from app.services import scores as service


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "SCORE_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")


@pytest.fixture
def model(monkeypatch):
    """Answer every scoring call with a fixed reply, and count the calls."""
    calls: list[str] = []

    def install(reply: str | Exception = "7.4"):
        async def fake(system: str, user: str, **kwargs):
            calls.append(user)
            if isinstance(reply, Exception):
                raise reply
            return ai.Completion(text=reply, tokens=4)

        monkeypatch.setattr(service.ai, "complete", fake)
        return calls

    return install


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


# --- reading the model's answer ------------------------------------------


def test_a_bare_number_is_read() -> None:
    assert service.parse("8.8") == Decimal("8.8")
    assert service.parse("10") == Decimal("10.0")
    assert service.parse("0.0") == Decimal("0.0")


def test_a_number_wrapped_in_words_is_still_read() -> None:
    # Cheaper than a retry when the model adds a label of its own.
    assert service.parse("Score: 6.2") == Decimal("6.2")
    assert service.parse("7.1.") == Decimal("7.1")


def test_an_answer_that_is_not_a_score_is_refused() -> None:
    for reply in ("", "excellent", "11.0", "-3", "100"):
        assert service.parse(reply) is None


def test_a_finer_answer_is_rounded_to_one_place() -> None:
    assert service.parse("7.46") == Decimal("7.5")


# --- what gets scored -----------------------------------------------------


async def test_a_posted_pulse_is_scored_and_comes_back_with_it(
    client, make_user, as_user, model
) -> None:
    model("8.3")
    user = await make_user("writer")
    created = await post(client, user, as_user, content="something worth reading")

    # Scoring runs after the response, so the post itself carries none yet.
    assert created.json()["score"] is None

    fetched = await client.get(
        f"/api/v1/pulses/{created.json()['id']}", headers=as_user(user)
    )
    assert fetched.json()["score"] == 8.3


async def test_the_score_is_stored_as_its_own_row(
    client, db, make_user, as_user, model
) -> None:
    model("6.9")
    user = await make_user("writer")
    created = await post(client, user, as_user, content="a thought")

    row = await db.scalar(
        select(PulseScore).where(PulseScore.pulse_id == created.json()["id"])
    )
    assert row is not None
    assert row.value == Decimal("6.9")
    assert row.source == ScoreSource.AI
    # No person gave this one, and the model that did is recorded.
    assert row.rater_id is None
    assert row.model == settings.OPENAI_MODEL


async def test_a_repost_is_not_scored(client, db, make_user, as_user, model) -> None:
    calls = model()
    author = await make_user("writer")
    reader = await make_user("reader")
    original = (await post(client, author, as_user, content="worth repeating")).json()
    await client.post(f"/api/v1/pulses/{original['id']}/repulse", headers=as_user(reader))

    # A repost carries no words of its own, so it is not sent to be judged:
    # the original was, once, when it was written.
    repost_id = (await db.scalar(select(func.max(Pulse.id)))) or 0
    assert repost_id != original["id"]
    assert (
        await db.scalar(select(PulseScore).where(PulseScore.pulse_id == repost_id))
    ) is None
    assert calls == ["worth repeating"]


async def test_a_pulse_is_scored_once(client, db, make_user, as_user, model) -> None:
    calls = model("5.5")
    user = await make_user("writer")
    created = await post(client, user, as_user, content="only judged once")

    # Posting scored it once; asking again reads back what is already there.
    again = await service.score_pulse(db, created.json()["id"])

    assert again == Decimal("5.5")
    assert len(calls) == 1


async def test_nothing_is_scored_while_the_feature_is_off(
    client, make_user, as_user, model, monkeypatch
) -> None:
    calls = model()
    monkeypatch.setattr(settings, "SCORE_ENABLED", False)
    user = await make_user("writer")
    created = await post(client, user, as_user, content="unjudged")

    fetched = await client.get(
        f"/api/v1/pulses/{created.json()['id']}", headers=as_user(user)
    )
    assert fetched.json()["score"] is None
    assert calls == []


async def test_the_day_has_a_ceiling(
    client, db, make_user, as_user, model, monkeypatch
) -> None:
    # Past the ceiling a pulse stays unscored, which the interface allows for.
    monkeypatch.setattr(settings, "SCORE_MAX_PER_DAY", 1)
    model("4.2")
    user = await make_user("writer")
    first = await post(client, user, as_user, content="the first thing")
    second = await post(client, user, as_user, content="the second thing")

    scored = await client.get(f"/api/v1/pulses/{first.json()['id']}", headers=as_user(user))
    unscored = await client.get(
        f"/api/v1/pulses/{second.json()['id']}", headers=as_user(user)
    )
    assert scored.json()["score"] == 4.2
    assert unscored.json()["score"] is None


# --- when the model does not cooperate ------------------------------------


async def test_an_unreadable_answer_leaves_the_pulse_unscored(
    client, db, make_user, as_user, model
) -> None:
    model("I would rather not say")
    user = await make_user("writer")
    created = await post(client, user, as_user, content="hello")

    assert (
        await db.scalar(
            select(PulseScore).where(PulseScore.pulse_id == created.json()["id"])
        )
    ) is None


async def test_a_failed_call_never_reaches_the_caller(
    client, db, make_user, as_user, model
) -> None:
    model(ai.AiError("rate limited", retryable=True))
    user = await make_user("writer")
    created = await post(client, user, as_user, content="hello")

    # A pulse that could not be scored is still a posted pulse.
    assert created.status_code == 201
    assert await service.score_pulse(db, created.json()["id"]) is None


async def test_scoring_in_the_background_swallows_everything(
    client, make_user, as_user, model
) -> None:
    model(ai.AiError("gone"))
    user = await make_user("writer")
    created = await post(client, user, as_user, content="hello")

    # The background task is the one place a raise would be unhandled.
    await service.score_in_background(created.json()["id"])
