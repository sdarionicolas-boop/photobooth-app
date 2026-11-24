import logging

from fastapi import APIRouter, HTTPException

from ...container import container
from ...services.processing import ActionType
from ...utils.exceptions import ProcessMachineOccupiedError
from .background import list_backgrounds

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("/{action_type}/{index}")
def api_trigger_model(action_type: ActionType, index: int = 0, background: str | None = None):
    """Trigger an action.

    background (single images and collages only): file from /api/background/ chosen by the guest before the capture,
    or an empty value for "no background" (picture as captured). Omit to use the action's configured background.
    """
    if background is not None:
        if action_type not in ("image", "collage"):
            raise HTTPException(status_code=406, detail="a background can be chosen for single images and collages only")
        if background and background not in {c.file for c in list_backgrounds()}:
            raise HTTPException(status_code=406, detail="background not available")

    try:
        if background is None:
            container.processing_service.trigger_action(action_type, index)
        else:
            container.processing_service.trigger_action(action_type, index, background=background)

    except ProcessMachineOccupiedError as exc:
        # raised if processingservice not idle
        raise HTTPException(status_code=400, detail=f"only one capture at a time allowed: {exc}") from exc
    except Exception as exc:
        # other errors
        logger.critical(exc, exc_info=exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
