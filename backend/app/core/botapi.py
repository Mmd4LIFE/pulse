"""One place to talk to the Telegram Bot API.

Several parts of Pulse need the bot: mirroring pulses into a channel, and
preparing a message for the user to share. They share the token, the timeout,
and the way Telegram reports failure, so they share this.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

API_ROOT = "https://api.telegram.org"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class TelegramApiError(Exception):
    """A call to the Bot API failed."""

    def __init__(self, description: str, *, status: int | None = None) -> None:
        self.description = description
        self.status = status
        super().__init__(description)


async def call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke ``method`` and return its ``result``, or raise."""
    url = f"{API_ROOT}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise TelegramApiError(f"Could not reach Telegram: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramApiError("Telegram returned an unreadable response") from exc

    if not body.get("ok"):
        raise TelegramApiError(
            str(body.get("description") or "Telegram rejected the request"),
            status=response.status_code,
        )
    result = body.get("result")
    return result if isinstance(result, dict) else {}
