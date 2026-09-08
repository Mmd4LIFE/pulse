"""Model package. Importing it registers every table on ``Base.metadata``."""

from app.db.base import Base
from app.models.hashtag import Hashtag, Mention, PulseHashtag
from app.models.media import Media
from app.models.notification import Notification, NotificationType
from app.models.pulse import Pulse
from app.models.social import Block, Bookmark, Follow, Like
from app.models.user import User

__all__ = [
    "Base",
    "Block",
    "Bookmark",
    "Follow",
    "Hashtag",
    "Like",
    "Media",
    "Mention",
    "Notification",
    "NotificationType",
    "Pulse",
    "PulseHashtag",
    "User",
]
