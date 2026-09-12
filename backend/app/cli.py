"""Managing automated accounts from the command line.

Deliberately not an HTTP API. Creating accounts that read as people is an
operator action, and giving it an endpoint would mean designing an
authorisation story for it; a command that only someone with shell access can
run needs none.

  python -m app.cli create --topic "type design" --language fa
  python -m app.cli list
  python -m app.cli pause @handle       /  resume @handle
  python -m app.cli delete @handle
  python -m app.cli run-once
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, select, update

from app.core.logging import configure_logging
from app.db.session import SessionLocal, engine
from app.models import Persona, User
from app.services import ai
from app.services import personas as persona_service


async def _by_handle(db, handle: str) -> Persona | None:
    handle = handle.lstrip("@")
    return await db.scalar(
        select(Persona)
        .join(User, User.id == Persona.user_id)
        .where(User.username.ilike(handle))
    )


async def cmd_create(args: argparse.Namespace) -> int:
    if not ai.is_configured():
        print("AI_ENABLED is off or OPENAI_API_KEY is unset.", file=sys.stderr)
        return 1

    async with SessionLocal() as db:
        for index in range(args.count):
            try:
                persona = await persona_service.create_persona(
                    db,
                    topic=args.topic,
                    language=args.language,
                    post_every_minutes=args.every,
                    reply_chance=args.reply_chance,
                    like_chance=args.like_chance,
                    repulse_chance=args.repulse_chance,
                )
            except ai.AiError as exc:
                print(f"  failed: {exc}", file=sys.stderr)
                return 1

            followed = await persona_service.follow_each_other(db, persona)
            print(
                f"  @{persona.user.username:<20} {persona.user.display_name:<26} "
                f"follows {followed}"
            )
            if args.post_now:
                pulse = await persona_service.write_post(db, persona)
                if pulse:
                    print(f"      posted: {pulse.content[:90]}")
            if index + 1 < args.count:
                await asyncio.sleep(1)
    return 0


async def cmd_list(_: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        rows = list((await db.scalars(select(Persona).order_by(Persona.id))).unique().all())
        if not rows:
            print("No automated accounts.")
            return 0
        print(
            f"{'handle':<22}{'state':<9}{'topic':<26}{'posts':>6}{'replies':>8}{'tokens':>9}"
        )
        for persona in rows:
            print(
                f"@{persona.user.username:<21}"
                f"{'active' if persona.is_active else 'paused':<9}"
                f"{persona.topic[:24]:<26}"
                f"{persona.posts_made:>6}{persona.replies_made:>8}{persona.tokens_used:>9}"
            )
            if persona.last_error:
                print(f"    last error: {persona.last_error}")
    return 0


async def _set_active(handle: str, active: bool) -> int:
    async with SessionLocal() as db:
        persona = await _by_handle(db, handle)
        if persona is None:
            print(f"No automated account @{handle.lstrip('@')}.", file=sys.stderr)
            return 1
        await db.execute(
            update(Persona).where(Persona.id == persona.id).values(is_active=active)
        )
        await db.commit()
        print(f"@{persona.user.username} {'resumed' if active else 'paused'}.")
    return 0


async def cmd_pause(args: argparse.Namespace) -> int:
    return await _set_active(args.handle, False)


async def cmd_resume(args: argparse.Namespace) -> int:
    return await _set_active(args.handle, True)


async def cmd_delete(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        persona = await _by_handle(db, args.handle)
        if persona is None:
            print(f"No automated account @{args.handle.lstrip('@')}.", file=sys.stderr)
            return 1
        username = persona.user.username
        # Deleting the user cascades to the persona, its pulses and its edges.
        await db.execute(delete(User).where(User.id == persona.user_id))
        await db.commit()
        print(f"@{username} and everything it posted have been deleted.")
    return 0


async def cmd_run_once(_: argparse.Namespace) -> int:
    from app.workers.personas import tick

    totals = await tick()
    print(
        f"accounts={totals['accounts']} posted={totals['posted']} "
        f"replied={totals['replied']} liked={totals['liked']} "
        f"repulsed={totals['repulsed']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="invent one or more automated accounts")
    create.add_argument("--topic", required=True, help="what they post about")
    create.add_argument("--language", default="en", help="en, fa, ar, …")
    create.add_argument("--count", type=int, default=1)
    create.add_argument("--every", type=int, default=180, help="minutes between posts")
    create.add_argument("--reply-chance", type=float, default=0.25)
    create.add_argument("--like-chance", type=float, default=0.5)
    create.add_argument("--repulse-chance", type=float, default=0.08)
    create.add_argument("--post-now", action="store_true", help="post once immediately")
    create.set_defaults(run=cmd_create)

    sub.add_parser("list", help="show every automated account").set_defaults(run=cmd_list)

    for name, fn, help_text in (
        ("pause", cmd_pause, "stop an account acting"),
        ("resume", cmd_resume, "let it act again"),
        ("delete", cmd_delete, "remove it and everything it posted"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("handle")
        p.set_defaults(run=fn)

    sub.add_parser("run-once", help="run a single worker tick now").set_defaults(
        run=cmd_run_once
    )
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()

    async def runner() -> int:
        try:
            return await args.run(args)
        finally:
            await engine.dispose()

    return asyncio.run(runner())


if __name__ == "__main__":
    raise SystemExit(main())
