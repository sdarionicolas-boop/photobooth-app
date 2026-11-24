import io
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm.attributes import flag_modified

from ...container import container
from ...services.mediaprocessing.processes import process_phase1images
from ...utils.media_encode import encode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signature", tags=["signature"])

MAX_SIGNATURE_BYTES = 10 * 1024 * 1024


@router.post("/{mediaitem_id}")
def api_apply_signature(
    mediaitem_id: UUID,
    signature_png: Annotated[bytes, Body(media_type="image/png")],
):
    """Overlay a hand-drawn signature (transparent PNG covering the whole picture) on an image or collage mediaitem.

    Single images are rebuilt from the captured original, so signing again replaces the previous signature.
    Collages (and other items without captured original) are signed as they are, so strokes add up.
    """

    if len(signature_png) > MAX_SIGNATURE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="signature image too large")

    try:
        signature = Image.open(io.BytesIO(signature_png)).convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"signature is not a valid image: {exc}") from exc

    try:
        mediaitem = container.mediacollection_service.get_item(item_id=mediaitem_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{mediaitem_id=} cannot be found. {exc}") from exc

    if mediaitem.media_type not in ("image", "collage"):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="only images and collages can be signed")

    try:
        if mediaitem.captured_original is not None:
            # rebuild the processed picture from the original (applies the stored filter again) ...
            process_phase1images(mediaitem.captured_original, mediaitem)

        # ... and put the signature on top.
        with Image.open(mediaitem.processed) as processed:
            base = processed.convert("RGBA")
        if signature.size != base.size:
            signature = signature.resize(base.size, Image.Resampling.LANCZOS)
        signed = Image.alpha_composite(base, signature).convert("RGB")
        encode([signed], mediaitem.processed)

        # the revision is only incremented (cache busting) if sqlalchemy considers the item changed. no db field changes
        # when signing, so flag explicitly, otherwise clients would keep showing the cached unsigned picture.
        flag_modified(mediaitem, "pipeline_config")

        # update at last because clients get their sse update (and bust their cache) only now
        container.mediacollection_service.update_item(mediaitem)
    except Exception as exc:
        logger.error(f"apply signature failed, reason: {exc}", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"apply signature failed, reason: {exc}.") from exc
