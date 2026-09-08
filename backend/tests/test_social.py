"""The follow graph, feeds, blocks, and notifications."""

from __future__ import annotations


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


async def test_following_updates_both_counters(client, make_user, as_user) -> None:
    a = await make_user("alice")
    await make_user("bob")

    assert (
        await client.post("/api/v1/users/bob/follow", headers=as_user(a))
    ).status_code == 200
    again = await client.post("/api/v1/users/bob/follow", headers=as_user(a))
    assert again.json()["message"] == "Already following."

    profile = (await client.get("/api/v1/users/bob", headers=as_user(a))).json()
    assert profile["followers_count"] == 1
    assert profile["is_following"] is True

    mine = (await client.get("/api/v1/users/alice", headers=as_user(a))).json()
    assert mine["following_count"] == 1

    await client.delete("/api/v1/users/bob/follow", headers=as_user(a))
    profile = (await client.get("/api/v1/users/bob", headers=as_user(a))).json()
    assert profile["followers_count"] == 0
    assert profile["is_following"] is False


async def test_you_cannot_follow_yourself(client, make_user, as_user) -> None:
    a = await make_user("alice")
    assert (
        await client.post("/api/v1/users/alice/follow", headers=as_user(a))
    ).status_code == 403


async def test_home_feed_shows_followed_accounts_and_yourself(
    client, make_user, as_user
) -> None:
    me, followed, stranger = (
        await make_user("me"),
        await make_user("followed"),
        await make_user("stranger"),
    )
    await client.post("/api/v1/users/followed/follow", headers=as_user(me))

    await post(client, stranger, as_user, content="from a stranger")
    await post(client, followed, as_user, content="from someone I follow")
    await post(client, me, as_user, content="from me")

    feed = (await client.get("/api/v1/feed/home", headers=as_user(me))).json()
    contents = [p["content"] for p in feed["items"]]
    assert contents == ["from me", "from someone I follow"]


async def test_home_feed_omits_replies(client, make_user, as_user) -> None:
    me, other = await make_user("me"), await make_user("other")
    await client.post("/api/v1/users/other/follow", headers=as_user(me))
    root = (await post(client, other, as_user, content="root")).json()
    await post(client, other, as_user, content="a reply", reply_to_id=root["id"])

    feed = (await client.get("/api/v1/feed/home", headers=as_user(me))).json()
    assert [p["content"] for p in feed["items"]] == ["root"]


async def test_feed_pages_with_a_stable_cursor(client, make_user, as_user) -> None:
    me = await make_user("me")
    for i in range(7):
        await post(client, me, as_user, content=f"pulse {i}")

    first = (await client.get("/api/v1/feed/home?limit=3", headers=as_user(me))).json()
    assert len(first["items"]) == 3
    assert first["has_more"] is True

    second = (
        await client.get(
            f"/api/v1/feed/home?limit=3&cursor={first['next_cursor']}",
            headers=as_user(me),
        )
    ).json()
    assert len(second["items"]) == 3
    # Pages must not overlap.
    assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}


async def test_blocking_hides_content_both_ways(client, make_user, as_user) -> None:
    a, b = await make_user("alice"), await make_user("bob")
    await client.post("/api/v1/users/bob/follow", headers=as_user(a))
    await post(client, b, as_user, content="from bob")

    feed = (await client.get("/api/v1/feed/home", headers=as_user(a))).json()
    assert len(feed["items"]) == 1

    await client.post("/api/v1/users/bob/block", headers=as_user(a))

    # The block drops the follow edge and hides bob from alice's explore feed.
    explore = (await client.get("/api/v1/feed/explore", headers=as_user(a))).json()
    assert explore["items"] == []
    # ...and hides alice from bob, who did not do the blocking, while leaving
    # bob's own pulses visible to him.
    await post(client, a, as_user, content="from alice")
    explore_b = (await client.get("/api/v1/feed/explore", headers=as_user(b))).json()
    assert [p["content"] for p in explore_b["items"]] == ["from bob"]

    profile = (await client.get("/api/v1/users/bob", headers=as_user(a))).json()
    assert profile["is_following"] is False


async def test_blocking_prevents_a_follow(client, make_user, as_user) -> None:
    a, b = await make_user("alice"), await make_user("bob")
    await client.post("/api/v1/users/bob/block", headers=as_user(a))
    assert (
        await client.post("/api/v1/users/alice/follow", headers=as_user(b))
    ).status_code == 403


async def test_interactions_raise_notifications(client, make_user, as_user) -> None:
    author, fan = await make_user("author"), await make_user("fan")
    pulse_id = (await post(client, author, as_user, content="Notice me")).json()["id"]

    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(fan))
    await post(client, fan, as_user, content="nice", reply_to_id=pulse_id)
    await client.post("/api/v1/users/author/follow", headers=as_user(fan))

    inbox = (await client.get("/api/v1/notifications", headers=as_user(author))).json()
    kinds = {n["type"] for n in inbox["items"]}
    assert kinds == {"like", "reply", "follow"}
    assert all(n["actor"]["username"] == "fan" for n in inbox["items"])

    unread = (
        await client.get("/api/v1/notifications/unread-count", headers=as_user(author))
    ).json()
    assert unread["count"] == 3

    await client.post("/api/v1/notifications/read-all", headers=as_user(author))
    unread = (
        await client.get("/api/v1/notifications/unread-count", headers=as_user(author))
    ).json()
    assert unread["count"] == 0


async def test_you_are_not_notified_about_your_own_actions(
    client, make_user, as_user
) -> None:
    me = await make_user("me")
    pulse_id = (await post(client, me, as_user, content="mine")).json()["id"]
    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(me))
    await post(client, me, as_user, content="self reply", reply_to_id=pulse_id)

    inbox = (await client.get("/api/v1/notifications", headers=as_user(me))).json()
    assert inbox["items"] == []


async def test_mentioning_someone_notifies_them(client, make_user, as_user) -> None:
    author, mentioned = await make_user("author"), await make_user("target")
    await post(client, author, as_user, content="hey @target look at this")

    inbox = (await client.get("/api/v1/notifications", headers=as_user(mentioned))).json()
    assert [n["type"] for n in inbox["items"]] == ["mention"]


async def test_profile_can_be_renamed_but_not_to_a_taken_handle(
    client, make_user, as_user
) -> None:
    a = await make_user("alice")
    await make_user("bob")

    ok = await client.patch(
        "/api/v1/users/me", json={"username": "ada", "bio": "hello"}, headers=as_user(a)
    )
    assert ok.status_code == 200
    assert ok.json()["username"] == "ada"

    clash = await client.patch(
        "/api/v1/users/me", json={"username": "bob"}, headers=as_user(a)
    )
    assert clash.status_code == 409

    reserved = await client.patch(
        "/api/v1/users/me", json={"username": "admin"}, headers=as_user(a)
    )
    assert reserved.status_code == 422

    bad = await client.patch(
        "/api/v1/users/me", json={"username": "a b"}, headers=as_user(a)
    )
    assert bad.status_code == 422


async def test_search_finds_users_pulses_and_hashtags(client, make_user, as_user) -> None:
    user = await make_user("searchable", display_name="Findable Person")
    await post(client, user, as_user, content="a very findable #topic")

    results = (await client.get("/api/v1/search?q=findable")).json()
    assert [u["username"] for u in results["users"]] == ["searchable"]
    assert len(results["pulses"]) == 1

    tags = (await client.get("/api/v1/search?q=topic")).json()
    assert [h["tag"] for h in tags["hashtags"]] == ["topic"]


async def test_search_treats_wildcards_literally(client, make_user, as_user) -> None:
    user = await make_user("plain")
    await post(client, user, as_user, content="a normal pulse")
    # "%" must not match everything.
    results = (await client.get("/api/v1/search/pulses?q=%25")).json()
    assert results["items"] == []


async def test_profile_tabs_split_pulses_replies_and_likes(
    client, make_user, as_user
) -> None:
    author, other = await make_user("author"), await make_user("other")
    root = (await post(client, other, as_user, content="other's root")).json()
    own = (await post(client, author, as_user, content="my pulse")).json()
    await post(client, author, as_user, content="my reply", reply_to_id=root["id"])
    await client.post(f"/api/v1/pulses/{root['id']}/like", headers=as_user(author))

    pulses = (await client.get("/api/v1/users/author/pulses")).json()
    assert [p["id"] for p in pulses["items"]] == [own["id"]]

    replies = (await client.get("/api/v1/users/author/replies")).json()
    assert [p["content"] for p in replies["items"]] == ["my reply"]

    likes = (await client.get("/api/v1/users/author/likes")).json()
    assert [p["id"] for p in likes["items"]] == [root["id"]]


async def test_the_same_pulse_is_not_repeated_for_each_reposter(
    client, make_user, as_user
) -> None:
    """Three followees boosting one pulse should still render one card."""
    me = await make_user("me")
    author = await make_user("author")
    boosters = [await make_user(f"booster{i}") for i in range(3)]

    pulse_id = (await post(client, author, as_user, content="the one pulse")).json()["id"]
    for booster in boosters:
        await client.post(f"/api/v1/users/{booster.username}/follow", headers=as_user(me))
        await client.post(f"/api/v1/pulses/{pulse_id}/repulse", headers=as_user(booster))

    feed = (await client.get("/api/v1/feed/home", headers=as_user(me))).json()
    assert [p["content"] for p in feed["items"]] == ["the one pulse"]
