"""Model package. Importing it registers every table on ``Base.metadata``."""

from app.db.base import Base
from app.models.channel import Channel
from app.models.hashtag import Hashtag, Mention, PulseHashtag
from app.models.media import Media
from app.models.notification import Notification, NotificationType
from app.models.persona import Persona
from app.models.pulse import Pulse
from app.models.social import Block, Bookmark, Follow, FollowRequest, Like
from app.models.user import User

__all__ = [
    "Base",
    "Block",
    "Bookmark",
    "Channel",
    "Follow",
    "FollowRequest",
    "Hashtag",
    "Like",
    "Media",
    "Mention",
    "Notification",
    "NotificationType",
    "Persona",
    "Pulse",
    "PulseHashtag",
    "User",
]
