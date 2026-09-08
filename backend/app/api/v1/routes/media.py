"""Image uploads."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import ValidationError
from app.schemas.pulse import MediaOut
from app.services import media as media_service
from app.services.serializers import media_url

router = APIRouter(prefix="/media", tags=["media"])


@router.post("", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None, max_length=420),
) -> MediaOut:
    """Upload an image and get back an id to attach to a pulse."""
    # Read at most one byte over the limit so an oversized upload is rejected
    # without buffering the whole thing.
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError(f"Images must be smaller than {limit_mb} MB.")

    item = await media_service.store_upload(db, user, data, alt_text)
    return MediaOut(
        id=item.id,
        url=media_url(item),
        mime_type=item.mime_type,
        width=item.width,
        height=item.height,
        alt_text=item.alt_text,
    )
