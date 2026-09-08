"""The Pulse Telegram bot.

Its only real job is to be the door to the Mini App: it publishes the menu
button, answers /start with a launch button, and turns deep links such as
``t.me/bot?start=pulse_42`` into a direct link into the app.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from config import get_settings

settings = get_settings()
logger = logging.getLogger("pulse.bot")

dp = Dispatcher()

# Deep links look like "pulse_123" (a pulse) or "u_alice" (a profile).
DEEP_LINK_RE = re.compile(r"^(pulse|u)_([A-Za-z0-9_]{1,32})$")


def launch_keyboard(path: str = "/", label: str = "Open Pulse") -> InlineKeyboardMarkup:
    url = settings.PUBLIC_WEB_URL.rstrip("/") + path
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))]
        ]
    )


@dp.message(CommandStart())
async def on_start(message: Message, command: CommandObject) -> None:
    payload = (command.args or "").strip()
    match = DEEP_LINK_RE.match(payload) if payload else None

    if match:
        kind, value = match.groups()
        path = f"/pulse/{value}" if kind == "pulse" else f"/u/{value}"
        label = "Open pulse" if kind == "pulse" else f"Open @{value}"
        await message.answer(
            "Here you go — tap to open it in Pulse.",
            reply_markup=launch_keyboard(path, label),
        )
        return

    name = html.quote(message.from_user.full_name if message.from_user else "there")
    await message.answer(
        f"Hey {name} 👋\n\n"
        f"<b>Pulse</b> is a short-form feed that lives right here in Telegram.\n\n"
        "• Post up to 280 characters, with images\n"
        "• Follow people and read a timeline that is just theirs\n"
        "• Reply, quote, repulse, bookmark\n\n"
        "Tap below to open it.",
        reply_markup=launch_keyboard(),
    )


@dp.message(F.text == "/help")
async def on_help(message: Message) -> None:
    await message.answer(
        "<b>Pulse commands</b>\n\n"
        "/start — open the app\n"
        "/help — this message\n\n"
        "Everything else happens inside the Mini App.",
        reply_markup=launch_keyboard(),
    )


@dp.message()
async def on_anything_else(message: Message) -> None:
    await message.answer(
        "Pulse lives in the Mini App — tap below to jump in.",
        reply_markup=launch_keyboard(),
    )


async def publish_menu_button(bot: Bot) -> None:
    """Put a permanent "Open Pulse" button in the chat's menu."""
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Open Pulse",
                web_app=WebAppInfo(url=settings.PUBLIC_WEB_URL),
            )
        )
        logger.info("menu button set to %s", settings.PUBLIC_WEB_URL)
    except Exception as exc:  # noqa: BLE001 - startup must not be fatal here
        logger.warning("could not set the menu button: %s", exc)


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    me = await bot.get_me()
    logger.info("starting as @%s (%s)", me.username, me.id)
    await publish_menu_button(bot)

    # Drop anything queued while the bot was down; the app is the source of truth.
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("stopped")
