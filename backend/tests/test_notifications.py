"""The grouped notification inbox."""

from __future__ import annotations


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


async def inbox(client, user, as_user, tab="all"):
    response = await client.get(f"/api/v1/notifications?tab={tab}", headers=as_user(user))
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_many_likes_on_one_pulse_are_one_row(client, make_user, as_user) -> None:
    """Forty people liking a pulse is one thing that happened, not forty."""
    author = await make_user("author")
    pulse_id = (await post(client, author, as_user, content="Popular")).json()["id"]

    for i in range(5):
        fan = await make_user(f"fan{i}")
        await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(fan))

    items = await inbox(client, author, as_user)
    assert len(items) == 1
    row = items[0]
    assert row["type"] == "like"
    assert row["actor_count"] == 5
    # It shows a few faces and counts the rest, rather than listing everyone.
    assert len(row["actors"]) == 3
    assert row["pulse"]["content"] == "Popular"


async def test_likes_on_different_pulses_stay_apart(client, make_user, as_user) -> None:
    author, fan = await make_user("author"), await make_user("fan")
    first = (await post(client, author, as_user, content="One")).json()["id"]
    second = (await post(client, author, as_user, content="Two")).json()["id"]

    await client.post(f"/api/v1/pulses/{first}/like", headers=as_user(fan))
    await client.post(f"/api/v1/pulses/{second}/like", headers=as_user(fan))

    items = await inbox(client, author, as_user)
    assert len(items) == 2
    assert {i["pulse"]["content"] for i in items} == {"One", "Two"}


async def test_replies_are_never_grouped(client, make_user, as_user) -> None:
    """Each carries words worth reading; collapsing them would hide them."""
    author = await make_user("author")
    pulse_id = (await post(client, author, as_user, content="Root")).json()["id"]

    for i in range(3):
        replier = await make_user(f"replier{i}")
        await post(client, replier, as_user, content=f"Reply {i}", reply_to_id=pulse_id)

    items = await inbox(client, author, as_user)
    assert len(items) == 3
    assert all(i["actor_count"] == 1 for i in items)
    assert {i["pulse"]["content"] for i in items} == {"Reply 0", "Reply 1", "Reply 2"}


async def test_likes_and_repulses_on_one_pulse_are_separate_rows(
    client, make_user, as_user
) -> None:
    author, fan = await make_user("author"), await make_user("fan")
    pulse_id = (await post(client, author, as_user, content="Both")).json()["id"]

    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(fan))
    await client.post(f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(fan))

    items = await inbox(client, author, as_user)
    assert {i["type"] for i in items} == {"like", "repulse"}


async def test_a_days_follows_collapse_together(client, make_user, as_user) -> None:
    target = await make_user("target")
    for i in range(4):
        follower = await make_user(f"follower{i}")
        await client.post("/api/v1/users/target/follow", headers=as_user(follower))

    items = await inbox(client, target, as_user)
    assert len(items) == 1
    assert items[0]["type"] == "follow"
    assert items[0]["actor_count"] == 4
    assert items[0]["pulse"] is None


# --- tabs ------------------------------------------------------------------


async def test_follow_requests_have_their_own_tab(client, make_user, as_user) -> None:
    """A queue of decisions is not a record of things that happened."""
    owner, fan, liker = (
        await make_user("owner"),
        await make_user("fan"),
        await make_user("liker"),
    )
    pulse_id = (await post(client, owner, as_user, content="Hello")).json()["id"]
    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(liker))

    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    all_tab = await inbox(client, owner, as_user, "all")
    assert "follow_request" not in {i["type"] for i in all_tab}

    requests = await inbox(client, owner, as_user, "requests")
    assert [i["type"] for i in requests] == ["follow_request"]
    assert requests[0]["actors"][0]["username"] == "fan"


async def test_the_mentions_tab_holds_only_what_was_written_to_you(
    client, make_user, as_user
) -> None:
    author, other = await make_user("author"), await make_user("other")
    pulse_id = (await post(client, author, as_user, content="Root")).json()["id"]

    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(other))
    await client.post("/api/v1/users/author/follow", headers=as_user(other))
    await post(client, other, as_user, content="A reply", reply_to_id=pulse_id)
    await post(client, other, as_user, content="hey @author")

    kinds = {i["type"] for i in await inbox(client, author, as_user, "mentions")}
    assert kinds == {"reply", "mention"}


# --- read state ------------------------------------------------------------


async def test_a_group_is_unread_until_every_part_of_it_is(
    client, make_user, as_user
) -> None:
    author = await make_user("author")
    pulse_id = (await post(client, author, as_user, content="Popular")).json()["id"]
    for i in range(3):
        fan = await make_user(f"fan{i}")
        await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(fan))

    assert (await inbox(client, author, as_user))[0]["is_read"] is False

    await client.post("/api/v1/notifications/read-all", headers=as_user(author))
    assert (await inbox(client, author, as_user))[0]["is_read"] is True


async def test_reading_one_tab_leaves_the_others_alone(client, make_user, as_user) -> None:
    """Opening Mentions must not make a pending request look attended to."""
    owner, fan, replier = (
        await make_user("owner"),
        await make_user("fan"),
        await make_user("replier"),
    )
    pulse_id = (await post(client, owner, as_user, content="Root")).json()["id"]
    await post(client, replier, as_user, content="A reply", reply_to_id=pulse_id)
    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    await client.post("/api/v1/notifications/read-all?tab=mentions", headers=as_user(owner))

    counts = (
        await client.get("/api/v1/notifications/unread", headers=as_user(owner))
    ).json()
    assert counts["mentions"] == 0
    assert counts["requests"] == 1


async def test_each_tab_reports_its_own_unread_count(client, make_user, as_user) -> None:
    owner, fan, liker = (
        await make_user("owner"),
        await make_user("fan"),
        await make_user("liker"),
    )
    pulse_id = (await post(client, owner, as_user, content="Root")).json()["id"]
    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(liker))
    await post(client, fan, as_user, content="nice", reply_to_id=pulse_id)

    counts = (
        await client.get("/api/v1/notifications/unread", headers=as_user(owner))
    ).json()
    assert counts["all"] == 2  # the like and the reply
    assert counts["mentions"] == 1  # the reply only
    assert counts["requests"] == 0


# --- paging ----------------------------------------------------------------


async def test_the_inbox_pages_without_repeating_a_row(client, make_user, as_user) -> None:
    author = await make_user("author")
    for i in range(7):
        pulse_id = (await post(client, author, as_user, content=f"Pulse {i}")).json()["id"]
        fan = await make_user(f"fan{i}")
        await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(fan))

    first = (
        await client.get("/api/v1/notifications?limit=3", headers=as_user(author))
    ).json()
    assert len(first["items"]) == 3 and first["has_more"] is True

    second = (
        await client.get(
            f"/api/v1/notifications?limit=3&cursor={first['next_cursor']}",
            headers=as_user(author),
        )
    ).json()
    assert not {i["key"] for i in first["items"]} & {i["key"] for i in second["items"]}


async def test_an_empty_inbox_is_an_empty_page(client, make_user, as_user) -> None:
    user = await make_user("nobody")
    assert await inbox(client, user, as_user) == []
    assert await inbox(client, user, as_user, "requests") == []


async def test_follow_requests_each_keep_their_own_row(client, make_user, as_user) -> None:
    """A decision is not an event: three grouped would mean one row, six buttons."""
    owner = await make_user("owner")
    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )
    for i in range(3):
        asker = await make_user(f"asker{i}")
        await client.post("/api/v1/users/owner/follow", headers=as_user(asker))

    rows = await inbox(client, owner, as_user, "requests")
    assert len(rows) == 3
    assert all(r["actor_count"] == 1 for r in rows)
    assert {r["actors"][0]["username"] for r in rows} == {"asker0", "asker1", "asker2"}


async def test_answering_one_request_leaves_the_others(client, make_user, as_user) -> None:
    owner = await make_user("owner")
    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )
    for i in range(3):
        asker = await make_user(f"asker{i}")
        await client.post("/api/v1/users/owner/follow", headers=as_user(asker))

    await client.post(
        "/api/v1/users/me/follow-requests/asker0/approve", headers=as_user(owner)
    )
    rows = await inbox(client, owner, as_user, "requests")
    assert {r["actors"][0]["username"] for r in rows} == {"asker1", "asker2"}
