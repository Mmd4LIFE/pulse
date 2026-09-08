"""Assembly of every v1 route."""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    channels,
    feed,
    media,
    notifications,
    pulses,
    search,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(pulses.router)
api_router.include_router(feed.router)
api_router.include_router(search.router)
api_router.include_router(notifications.router)
api_router.include_router(media.router)
api_router.include_router(channels.router)
