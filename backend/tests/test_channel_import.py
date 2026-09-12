"""Importing a channel's history from a Telegram Desktop export."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from app.services import channel_import as ci

CHAT_ID = -1001234567890
EXPORT_ID = 1234567890  # the same channel, as an export writes it


def export(messages, chat_id: int = EXPORT_ID) -> dict:
    return {
        "name": "My Channel",
        "type": "public_channel",
        "id": chat_id,
        "messages": messages,
    }


def message(mid: int, **over) -> dict:
    base = {
        "id": mid,
        "type": "message",
        "date": "2026-01-05T10:00:00",
        "date_unixtime": str(1767607200 + mid),
        "from": "My Channel",
        "text": f"Post number {mid}",
    }
    base.update(over)
    return base


def png_bytes(colour=(20, 90, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), colour).save(buf, format="PNG")
    return buf.getvalue()


def write_json(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_zip(tmp_path: Path, data: dict, media: dict[str, bytes] | None = None) -> Path:
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("result.json", json.dumps(data, ensure_ascii=False))
        for name, blob in (media or {}).items():
            archive.writestr(name, blob)
    return path


# --- parsing ---------------------------------------------------------------


def test_the_export_channel_id_maps_onto_the_bot_api_form() -> None:
    assert ci.chat_id_from_export(1234567890) == -1001234567890
    assert ci.chat_id_from_export("1234567890") == -1001234567890
    # Already in the -100 form, as some exports write it.
    assert ci.chat_id_from_export(-1001234567890) == -1001234567890
    assert ci.chat_id_from_export(None) is None
    assert ci.chat_id_from_export("not a number") is None


def test_text_runs_are_flattened_in_order() -> None:
    """Export text is a string, or a list mixing plain runs and entities."""
    assert ci.flatten_text("plain") == "plain"
    assert (
        ci.flatten_text(
            [
                "look at ",
                {"type": "link", "text": "example.com"},
                " and ",
                {"type": "hashtag", "text": "#tag"},
            ]
        )
        == "look at example.com and #tag"
    )
    assert ci.flatten_text(None) == ""
    assert ci.flatten_text([]) == ""


def test_persian_text_survives_flattening() -> None:
    runs = ["سلام ", {"type": "bold", "text": "دنیا"}, " #شروع"]
    assert ci.flatten_text(runs) == "سلام دنیا #شروع"


def test_reactions_are_carried_across_biggest_first() -> None:
    parsed = ci.parse_reactions(
        [
            {"type": "emoji", "count": 3, "emoji": "❤️"},
            {"type": "emoji", "count": 11, "emoji": "👍"},
        ]
    )
    assert parsed == [{"emoji": "👍", "count": 11}, {"emoji": "❤️", "count": 3}]


def test_custom_emoji_keep_their_count_under_a_neutral_mark() -> None:
    """A custom emoji cannot be drawn outside Telegram, but the tally is real."""
    parsed = ci.parse_reactions([{"type": "custom_emoji", "count": 7, "document_id": "1"}])
    assert parsed == [{"emoji": "⭐", "count": 7}]


def test_malformed_reactions_are_ignored() -> None:
    assert ci.parse_reactions(None) == []
    assert ci.parse_reactions("👍") == []
    assert ci.parse_reactions([{"count": 0, "emoji": "👍"}]) == []
    assert ci.parse_reactions([{"emoji": "👍"}]) == []


def test_service_events_are_skipped() -> None:
    data = export(
        [
            message(1),
            {"id": 2, "type": "service", "action": "pin_message"},
            message(3),
        ]
    )
    assert [m["id"] for m in ci.iter_messages(data)] == [1, 3]


def test_a_missing_file_reference_is_not_treated_as_media() -> None:
    """Exports write "(File not included...)" when media was left out."""
    assert (
        ci.media_paths(
            message(1, photo="(File not included. Change data exporting settings.)")
        )
        == []
    )
    assert ci.media_paths(message(1, photo="photos/photo_1.jpg")) == ["photos/photo_1.jpg"]
    # A video is not something Pulse can show.
    assert ci.media_paths(message(1, file="video_files/v.mp4")) == []


# --- importing -------------------------------------------------------------


@pytest.fixture
async def connected(db, make_user):
    from app.models import Channel

    owner = await make_user("owner")
    channel = Channel(
        owner_id=owner.id, chat_id=CHAT_ID, title="My Channel", username="mychannel"
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return owner, channel


async def test_posts_become_pulses_with_their_original_dates(
    db, connected, tmp_path, client, as_user
) -> None:
    owner, channel = connected
    path = write_json(tmp_path, export([message(1), message(2), message(3)]))

    created, updated = await ci.import_export(db, owner, channel, path)
    assert (created, updated) == (3, 0)

    tab = (await client.get("/api/v1/users/owner/channel")).json()
    assert [p["content"] for p in tab["items"]] == [
        "Post number 3",
        "Post number 2",
        "Post number 1",
    ]
    assert all(p["is_imported"] for p in tab["items"])
    assert all(p["source_date"] for p in tab["items"])


async def test_reimporting_updates_rather_than_duplicating(
    db, connected, tmp_path, client
) -> None:
    owner, channel = connected
    write = lambda msgs: write_json(tmp_path, export(msgs))  # noqa: E731

    await ci.import_export(db, owner, channel, write([message(1)]))
    created, updated = await ci.import_export(
        db,
        owner,
        channel,
        write(
            [
                message(
                    1,
                    text="Edited later",
                    reactions=[{"type": "emoji", "count": 4, "emoji": "🔥"}],
                )
            ]
        ),
    )
    assert (created, updated) == (0, 1)

    tab = (await client.get("/api/v1/users/owner/channel")).json()
    assert len(tab["items"]) == 1
    assert tab["items"][0]["content"] == "Edited later"
    assert tab["items"][0]["reactions"] == [{"emoji": "🔥", "count": 4}]


async def test_an_export_from_another_channel_is_refused(db, connected, tmp_path) -> None:
    """Otherwise anyone could publish someone else's channel as their own."""
    from app.core.errors import PermissionDeniedError

    owner, channel = connected
    path = write_json(tmp_path, export([message(1)], chat_id=999888777))

    with pytest.raises(PermissionDeniedError):
        await ci.import_export(db, owner, channel, path)


async def test_images_come_across_when_the_archive_has_them(
    db, connected, tmp_path, client
) -> None:
    owner, channel = connected
    path = write_zip(
        tmp_path,
        export([message(1, photo="photos/photo_1.jpg", width=60, height=40)]),
        {"photos/photo_1.jpg": png_bytes()},
    )

    created, _ = await ci.import_export(db, owner, channel, path)
    assert created == 1

    tab = (await client.get("/api/v1/users/owner/channel")).json()
    assert len(tab["items"][0]["media"]) == 1


async def test_a_json_only_upload_imports_the_text(db, connected, tmp_path, client) -> None:
    """Without the archive there are no image bytes, but the post still lands."""
    owner, channel = connected
    path = write_json(tmp_path, export([message(1, photo="photos/photo_1.jpg")]))

    created, _ = await ci.import_export(db, owner, channel, path)
    assert created == 1
    tab = (await client.get("/api/v1/users/owner/channel")).json()
    assert tab["items"][0]["media"] == []


async def test_a_long_post_is_cut_to_the_pulse_limit(db, connected, tmp_path) -> None:
    owner, channel = connected
    long_text = " ".join(["word"] * 200)
    path = write_json(tmp_path, export([message(1, text=long_text)]))

    await ci.import_export(db, owner, channel, path)

    from sqlalchemy import select

    from app.models import Pulse

    pulse = await db.scalar(select(Pulse).where(Pulse.source_message_id == 1))
    assert len(pulse.content) <= 280
    assert pulse.content.endswith("…")


async def test_empty_posts_are_skipped(db, connected, tmp_path, client) -> None:
    owner, channel = connected
    path = write_json(tmp_path, export([message(1, text=""), message(2)]))

    created, _ = await ci.import_export(db, owner, channel, path)
    assert created == 1


async def test_a_file_that_is_not_an_export_fails_clearly(db, connected, tmp_path) -> None:
    owner, channel = connected
    path = tmp_path / "junk.json"
    path.write_bytes(b"this is not json at all")

    with pytest.raises(ci.ChannelExportError, match="result.json"):
        await ci.import_export(db, owner, channel, path)


async def test_a_zip_without_a_result_json_fails_clearly(db, connected, tmp_path) -> None:
    owner, channel = connected
    path = tmp_path / "wrong.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", "nothing useful")

    with pytest.raises(ci.ChannelExportError, match="result.json"):
        await ci.import_export(db, owner, channel, path)


# --- how the archive behaves once it is in ---------------------------------


async def test_the_archive_stays_out_of_the_live_feeds(
    db, connected, tmp_path, client, as_user, make_user
) -> None:
    """A backfill of thousands of posts must not bury everyone's timeline."""
    owner, channel = connected
    reader = await make_user("reader")
    await client.post("/api/v1/users/owner/follow", headers=as_user(reader))

    await ci.import_export(
        db, owner, channel, write_json(tmp_path, export([message(i) for i in range(1, 6)]))
    )
    await client.post(
        "/api/v1/pulses", json={"content": "written here"}, headers=as_user(owner)
    )

    home = (await client.get("/api/v1/feed/home", headers=as_user(reader))).json()
    assert [p["content"] for p in home["items"]] == ["written here"]

    explore = (await client.get("/api/v1/feed/explore")).json()
    assert [p["content"] for p in explore["items"]] == ["written here"]

    # The main profile tab is for what was written here; the archive has its own.
    pulses = (await client.get("/api/v1/users/owner/pulses")).json()
    assert [p["content"] for p in pulses["items"]] == ["written here"]

    archive = (await client.get("/api/v1/users/owner/channel")).json()
    assert len(archive["items"]) == 5


async def test_imported_hashtags_do_not_drive_trends(
    db, connected, tmp_path, client
) -> None:
    owner, channel = connected
    await ci.import_export(
        db,
        owner,
        channel,
        write_json(tmp_path, export([message(1, text="old news #archive")])),
    )
    assert (await client.get("/api/v1/feed/trends")).json() == []


async def test_an_imported_pulse_can_still_be_opened_and_liked(
    db, connected, tmp_path, client, as_user, make_user
) -> None:
    owner, channel = connected
    reader = await make_user("reader")
    await ci.import_export(db, owner, channel, write_json(tmp_path, export([message(1)])))

    archive = (await client.get("/api/v1/users/owner/channel")).json()
    pulse_id = archive["items"][0]["id"]

    assert (await client.get(f"/api/v1/pulses/{pulse_id}")).status_code == 200
    assert (
        await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(reader))
    ).status_code == 200
