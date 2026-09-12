"""A small client for the chat completions API.

Deliberately thin: one call, a token count back, and errors that say whether
retrying is worth it. Everything about *what* to generate lives in the persona
service; this only knows how to ask.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class AiError(Exception):
    """A generation attempt failed."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        self.retryable = retryable
        super().__init__(message)


class AiDisabledError(AiError):
    """Generation is switched off, or no key is configured."""


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    tokens: int


def is_configured() -> bool:
    return bool(settings.AI_ENABLED and settings.OPENAI_API_KEY)


async def complete(
    system: str,
    user: str,
    *,
    max_tokens: int = 220,
    temperature: float = 0.95,
    attempts: int = 2,
) -> Completion:
    """Ask the model once, retrying only on failures that might pass."""
    if not is_configured():
        raise AiDisabledError(
            "Generation is off. Set AI_ENABLED and OPENAI_API_KEY to use it."
        )

    payload: dict[str, Any] = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"

    last: AiError = AiError("no attempt was made")
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.OPENAI_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            last = AiError(f"could not reach the model: {exc}", retryable=True)
        else:
            last = _read(response)
            if isinstance(last, Completion):
                return last

        if not last.retryable or attempt == attempts:
            break
        # A brief pause is enough for a rate limit or a blip; this runs in a
        # background worker, so there is nobody waiting on it.
        await asyncio.sleep(2 * attempt)

    raise last


def _read(response: httpx.Response) -> Completion | AiError:
    if response.status_code == 429:
        return AiError("rate limited by the model provider", retryable=True)
    if response.status_code >= 500:
        return AiError(f"model provider returned {response.status_code}", retryable=True)

    try:
        body = response.json()
    except ValueError:
        return AiError("model provider returned an unreadable response")

    if response.status_code >= 400:
        detail = (body.get("error") or {}).get("message") or response.text[:160]
        # A bad key or a missing model will not fix itself.
        return AiError(f"model provider rejected the request: {detail}")

    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return AiError("model provider returned no message")

    if not isinstance(text, str) or not text.strip():
        return AiError("model returned nothing usable")

    usage = body.get("usage") or {}
    return Completion(text=text.strip(), tokens=int(usage.get("total_tokens") or 0))
