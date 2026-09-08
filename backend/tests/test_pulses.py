"""Posting, threading, and interactions."""

from __future__ import annotations


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


async def test_create_and_read_a_pulse(client, make_user, as_user) -> None:
    user = await make_user("ada")
    response = await post(client, user, as_user, content="Hello #pulse world")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content"] == "Hello #pulse world"
    assert body["author"]["username"] == "ada"
    assert body["is_mine"] is True

    read = await client.get(f"/api/v1/pulses/{body['id']}")
    assert read.status_code == 200
    assert read.json()["id"] == body["id"]


async def test_a_pulse_needs_text_or_an_image(client, make_user, as_user) -> None:
    user = await make_user()
    assert (await post(client, user, as_user, content="   ")).status_code == 422


async def test_a_pulse_is_capped_at_280_characters(client, make_user, as_user) -> None:
    user = await make_user()
    assert (await post(client, user, as_user, content="x" * 281)).status_code == 422
    assert (await post(client, user, as_user, content="x" * 280)).status_code == 201


async def test_liking_is_idempotent_and_reversible(client, make_user, as_user) -> None:
    author, reader = await make_user("author"), await make_user("reader")
    pulse_id = (await post(client, author, as_user, content="Like me")).json()["id"]

    assert (
        await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(reader))
    ).status_code == 200
    # Liking twice must not double the counter.
    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(reader))

    read = await client.get(f"/api/v1/pulses/{pulse_id}", headers=as_user(reader))
    assert read.json()["like_count"] == 1
    assert read.json()["is_liked"] is True

    await client.delete(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(reader))
    read = await client.get(f"/api/v1/pulses/{pulse_id}", headers=as_user(reader))
    assert read.json()["like_count"] == 0
    assert read.json()["is_liked"] is False


async def test_replying_builds_a_thread(client, make_user, as_user) -> None:
    author, replier = await make_user("author"), await make_user("replier")
    root = (await post(client, author, as_user, content="Root")).json()
    reply = (
        await post(client, replier, as_user, content="Reply", reply_to_id=root["id"])
    ).json()

    thread = await client.get(f"/api/v1/pulses/{root['id']}/thread")
    body = thread.json()
    assert body["pulse"]["id"] == root["id"]
    assert body["pulse"]["reply_count"] == 1
    assert [r["id"] for r in body["replies"]] == [reply["id"]]

    # From the reply's point of view the root is an ancestor.
    child_thread = (await client.get(f"/api/v1/pulses/{reply['id']}/thread")).json()
    assert [a["id"] for a in child_thread["ancestors"]] == [root["id"]]


async def test_repulsing_appears_once_and_is_reversible(client, make_user, as_user) -> None:
    author, booster = await make_user("author"), await make_user("booster")
    pulse_id = (await post(client, author, as_user, content="Boost me")).json()["id"]

    assert (
        await client.post(f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(booster))
    ).status_code == 200
    second = await client.post(
        f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(booster)
    )
    assert second.json()["message"] == "Already repulsed."

    read = (await client.get(f"/api/v1/pulses/{pulse_id}", headers=as_user(booster))).json()
    assert read["repulse_count"] == 1
    assert read["is_repulsed"] is True

    await client.delete(f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(booster))
    read = (await client.get(f"/api/v1/pulses/{pulse_id}", headers=as_user(booster))).json()
    assert read["repulse_count"] == 0


async def test_a_repost_shows_the_original_credited_to_the_booster(
    client, make_user, as_user
) -> None:
    author, booster, reader = (
        await make_user("author"),
        await make_user("booster"),
        await make_user("reader"),
    )
    pulse_id = (await post(client, author, as_user, content="Original")).json()["id"]
    await client.post(f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(booster))
    await client.post("/api/v1/users/booster/follow", headers=as_user(reader))

    feed = (await client.get("/api/v1/feed/home", headers=as_user(reader))).json()
    entry = feed["items"][0]
    assert entry["content"] == "Original"
    assert entry["author"]["username"] == "author"
    assert entry["repulsed_by"]["username"] == "booster"


async def test_quoting_carries_the_quoted_pulse(client, make_user, as_user) -> None:
    author, quoter = await make_user("author"), await make_user("quoter")
    original = (await post(client, author, as_user, content="Original")).json()
    quote = (
        await post(
            client, quoter, as_user, content="Look at this", quote_of_id=original["id"]
        )
    ).json()

    assert quote["quote_of"]["id"] == original["id"]
    assert quote["quote_of"]["content"] == "Original"
    read = (await client.get(f"/api/v1/pulses/{original['id']}")).json()
    assert read["quote_count"] == 1


async def test_a_pulse_cannot_be_a_reply_and_a_quote(client, make_user, as_user) -> None:
    user = await make_user()
    a = (await post(client, user, as_user, content="a")).json()
    b = (await post(client, user, as_user, content="b")).json()
    response = await post(
        client, user, as_user, content="both", reply_to_id=a["id"], quote_of_id=b["id"]
    )
    assert response.status_code == 422


async def test_only_the_author_can_delete(client, make_user, as_user) -> None:
    author, other = await make_user("author"), await make_user("other")
    pulse_id = (await post(client, author, as_user, content="Mine")).json()["id"]

    assert (
        await client.delete(f"/api/v1/pulses/{pulse_id}", headers=as_user(other))
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/pulses/{pulse_id}", headers=as_user(author))
    ).status_code == 200
    assert (await client.get(f"/api/v1/pulses/{pulse_id}")).status_code == 404


async def test_deleting_a_reply_leaves_the_thread_intact(
    client, make_user, as_user
) -> None:
    author, replier = await make_user("author"), await make_user("replier")
    root = (await post(client, author, as_user, content="Root")).json()
    reply = (
        await post(client, replier, as_user, content="Reply", reply_to_id=root["id"])
    ).json()

    await client.delete(f"/api/v1/pulses/{reply['id']}", headers=as_user(replier))
    thread = (await client.get(f"/api/v1/pulses/{root['id']}/thread")).json()
    assert thread["replies"] == []
    assert thread["pulse"]["reply_count"] == 0


async def test_bookmarks_are_private_to_the_owner(client, make_user, as_user) -> None:
    author, saver = await make_user("author"), await make_user("saver")
    pulse_id = (await post(client, author, as_user, content="Save me")).json()["id"]

    await client.post(f"/api/v1/pulses/{pulse_id}/bookmark", headers=as_user(saver))
    saved = (await client.get("/api/v1/feed/bookmarks", headers=as_user(saver))).json()
    assert [p["id"] for p in saved["items"]] == [pulse_id]

    others = (await client.get("/api/v1/feed/bookmarks", headers=as_user(author))).json()
    assert others["items"] == []


async def test_hashtags_are_indexed_and_trend(client, make_user, as_user) -> None:
    user = await make_user()
    await post(client, user, as_user, content="Shipping #Pulse today")
    await post(client, user, as_user, content="more #pulse and #telegram")

    trends = (await client.get("/api/v1/feed/trends")).json()
    top = {t["tag"]: t["pulse_count"] for t in trends}
    assert top["pulse"] == 2  # case-folded into one trend
    assert top["telegram"] == 1

    tagged = (await client.get("/api/v1/feed/hashtag/pulse")).json()
    assert len(tagged["items"]) == 2
