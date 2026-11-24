"""
The util is very much inspired by https://github.com/danielgatis/rembg
Thank you!
"""

from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps
from PIL.Image import Image as PILImage

from .session_factory import new_session
from .sessions.base import BaseSession


def naive_cutout(img: PILImage, mask: PILImage) -> PILImage:
    empty = Image.new("RGBA", (img.size), 0)
    cutout = Image.composite(img, empty, mask)
    return cutout


def clean_mask(mask: PILImage, keep_ratio: float = 0.04, hole_ratio: float = 0.012, feather: int = 5) -> PILImage:
    """Tidy up the mask predicted by the model so the cutout looks cleaner:

    - small floating parts are dropped (stray blobs and specks that are not the person)
    - small holes inside the person are filled (for example bright spots in the hair)
    - the edge is softened slightly

    Args:
        mask: mask as predicted by the model, white = keep.
        keep_ratio: parts smaller than this fraction of the biggest part are dropped.
        hole_ratio: holes smaller than this fraction of the whole image are filled. Background reaching the image border is never filled.
        feather: width of the edge softening in pixel.
    """
    values = np.array(mask.convert("L"))
    area = values.shape[0] * values.shape[1]
    binary = (values >= 128).astype(np.uint8)

    # drop parts much smaller than the biggest one
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return mask.convert("L")  # nothing detected, nothing to clean
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i, a in enumerate(areas) if a >= max(keep_ratio * areas.max(), 0.0005 * area)]
    binary = np.isin(labels, keep).astype(np.uint8)

    # fill small holes: background parts that do not reach the border and are small
    count, labels, stats, _ = cv2.connectedComponentsWithStats((1 - binary).astype(np.uint8), connectivity=4)
    for i in range(1, count):
        x, y, w, h, a = stats[i]
        touches_border = x == 0 or y == 0 or x + w >= values.shape[1] or y + h >= values.shape[0]
        if not touches_border and a <= hole_ratio * area:
            binary[labels == i] = 1

    # soft edge, but never opaque where the model saw nothing at all
    cleaned = cv2.erode(binary * 255, np.ones((3, 3), np.uint8), iterations=1)
    if feather > 0:
        cleaned = cv2.GaussianBlur(cleaned, (0, 0), feather / 2)
    cleaned = np.minimum(cleaned, np.maximum(values, binary * 255).astype(np.uint8))

    return Image.fromarray(cleaned)


def remove(
    img: PILImage, session: BaseSession | None = None, only_mask: bool = False, cleanup: bool = False, *args: Any | None, **kwargs: Any | None
) -> PILImage:
    """
    Remove the background from an input image.
    With cleanup the predicted mask is tidied up first (see clean_mask).
    """

    # Fix image orientation
    ImageOps.exif_transpose(img, in_place=True)

    if session is None:
        session = new_session("modnet", *args, **kwargs)

    mask = session.predict(img, *args, **kwargs)
    if cleanup:
        mask = clean_mask(mask)

    if only_mask:
        return mask
    else:
        return naive_cutout(img, mask)
