import logging
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from ... import USERDATA_PATH
from ...container import container
from ...services.config.groups.actions import SingleImageProcessing
from ...services.mediaprocessing.processes import process_phase1images

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/background", tags=["background"])

BACKGROUND_DIRNAME = "backgrounds"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class BackgroundChoice(BaseModel):
    name: str
    file: str  # path as used in the pipeline config
    url: str  # url to display the background in the frontend


def list_backgrounds() -> list[BackgroundChoice]:
    """Images in any folder named 'backgrounds' below the userdata directory (symlinked folders like demoassets included)."""
    root = Path(USERDATA_PATH)
    choices: list[BackgroundChoice] = []

    for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
        if Path(dirpath).name.lower() != BACKGROUND_DIRNAME:
            continue
        for filename in sorted(filenames):
            path = Path(dirpath, filename)
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            choices.append(BackgroundChoice(name=path.stem, file=(root / relative).as_posix(), url=f"/userdata/{relative}"))

    return sorted(choices, key=lambda c: c.file)


@router.get("/")
def api_get_backgrounds() -> list[BackgroundChoice]:
    return list_backgrounds()


@router.patch("/{mediaitem_id}")
def api_apply_background(mediaitem_id: UUID, file: str | None = None):
    """Choose the background of a single image. Without file the picture is shown as captured (no background replaced).

    Only files returned by the list endpoint are accepted. The picture is rebuilt from the captured original,
    so a signature drawn before is gone and needs to be drawn again.
    """

    if file is not None and file not in {c.file for c in list_backgrounds()}:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="background not available")

    try:
        mediaitem = container.mediacollection_service.get_item(item_id=mediaitem_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{mediaitem_id=} cannot be found. {exc}") from exc

    if mediaitem.captured_original is None:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="only single images have a background")

    try:
        changes = (
            {"remove_background": True, "img_background_enable": True, "img_background_file": file}
            if file
            else {"remove_background": False, "img_background_enable": False, "img_background_file": None}
        )
        _config = SingleImageProcessing.model_validate(mediaitem.pipeline_config | changes)
        mediaitem.pipeline_config = _config.model_dump(mode="json")  # persisted along with the item; also bumps the revision

        flag_modified(mediaitem, "pipeline_config")  # bump revision even if the same background is chosen again

        process_phase1images(mediaitem.captured_original, mediaitem)

        # update at last because clients get their sse update (and bust their cache) only now
        container.mediacollection_service.update_item(mediaitem)
    except Exception as exc:
        logger.error(f"apply background failed, reason: {exc}", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"apply background failed, reason: {exc}.") from exc
