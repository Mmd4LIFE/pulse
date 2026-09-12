"""The loop that gives automated accounts their turns.

Wakes on a fixed tick, asks each active account whether it wants to do
anything, and stops for the day once the generation ceiling is reached. Runs as
its own process so a slow model call never occupies an API worker.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import signal

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal, engine
from app.models import Persona
from app.services import ai
from app.services import personas as persona_service

log = get_logger(__name__)


async def tick() -> dict[str, int]:
    """One pass over the active accounts."""
    totals = {"accounts": 0, "posted": 0, "replied": 0, "liked": 0, "repulsed": 0}

    async with SessionLocal() as db:
        used = await persona_service.generations_today(db)
        if used >= settings.AI_MAX_GENERATIONS_PER_DAY:
            log.info("persona_daily_cap_reached", used=used)
            return totals

        # Least recently acted first, so a large population comes round in turn
        # rather than the same few accounts being picked on every tick. The
        # limit is what keeps a tick shorter than the interval between ticks,
        # however many accounts exist.
        active = list(
            (
                await db.scalars(
                    select(Persona)
                    .where(Persona.is_active.is_(True))
                    .order_by(Persona.last_acted_at.asc().nullsfirst(), Persona.id)
                    .limit(settings.AI_ACCOUNTS_PER_TICK)
                )
            )
            .unique()
            .all()
        )
        if not active:
            return totals

        # Shuffled within the batch, so the same account is not always first to
        # a fresh pulse.
        random.shuffle(active)

        for persona in active:
            if (
                await persona_service.generations_today(db)
                >= settings.AI_MAX_GENERATIONS_PER_DAY
            ):
                log.info("persona_daily_cap_reached_mid_tick")
                break

            did = await persona_service.act(db, persona)
            totals["accounts"] += 1
            for key in ("posted", "replied", "liked", "repulsed"):
                totals[key] += did[key]

            # A human-ish gap between accounts, so a tick does not arrive as a
            # burst of identical timestamps.
            await asyncio.sleep(random.uniform(0.5, 3.0))

    return totals


async def main() -> None:
    configure_logging()

    if not ai.is_configured():
        log.warning(
            "persona_worker_idle",
            reason="AI_ENABLED is off or OPENAI_API_KEY is unset",
        )

    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stopping.set)

    log.info("persona_worker_started", tick_seconds=settings.AI_TICK_SECONDS)

    while not stopping.is_set():
        if ai.is_configured():
            try:
                totals = await tick()
                if totals["accounts"]:
                    log.info("persona_tick", **totals)
            except Exception as exc:
                log.exception("persona_tick_failed", error=str(exc))

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stopping.wait(), timeout=settings.AI_TICK_SECONDS)

    await engine.dispose()
    log.info("persona_worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
