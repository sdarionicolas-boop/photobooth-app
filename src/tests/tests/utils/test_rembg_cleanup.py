from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image, ImageDraw

from photobooth.appconfig import appconfig
from photobooth.services.config.groups.actions import SingleImageProcessing
from photobooth.services.mediaprocessing import processes
from photobooth.services.mediaprocessing.pipeline import PipelineStep
from photobooth.services.mediaprocessing.steps.image import RemovebgStep
from photobooth.utils.rembg.rembg import clean_mask, remove

SIZE = (400, 300)


def _mask(*shapes: tuple[str, tuple[int, int, int, int], int]) -> Image.Image:
    """shapes are drawn in order: ("rect", (x0, y0, x1, y1), value)"""
    mask = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(mask)
    for _kind, box, value in shapes:
        draw.rectangle(box, fill=value)
    return mask


def _at(mask: Image.Image, x: int, y: int) -> int:
    return mask.getpixel((x, y))


def test_keeps_the_person():
    cleaned = clean_mask(_mask(("rect", (100, 60, 300, 260), 255)))

    assert cleaned.size == SIZE
    assert cleaned.mode == "L"
    assert _at(cleaned, 200, 160) == 255
    assert _at(cleaned, 20, 20) == 0


def test_drops_small_floating_specks():
    speck = ("rect", (20, 20, 28, 28), 255)
    cleaned = clean_mask(_mask(("rect", (100, 60, 300, 260), 255), speck))

    assert _at(cleaned, 24, 24) == 0
    assert _at(cleaned, 200, 160) == 255


def test_keeps_a_sizeable_second_part():
    """for example a hand held away from the body"""
    cleaned = clean_mask(_mask(("rect", (100, 60, 250, 260), 255), ("rect", (300, 100, 360, 160), 255)))

    assert _at(cleaned, 330, 130) > 200


def test_fills_small_holes_inside_the_person():
    cleaned = clean_mask(_mask(("rect", (100, 60, 300, 260), 255), ("rect", (190, 100, 200, 110), 0)))

    assert _at(cleaned, 195, 105) > 200


def test_keeps_big_holes_open():
    """a real gap, for example between arm and body, stays a gap"""
    cleaned = clean_mask(_mask(("rect", (100, 60, 300, 260), 255), ("rect", (150, 100, 220, 170), 0)))

    assert _at(cleaned, 185, 135) < 50


def test_background_reaching_the_border_is_not_filled():
    notch = ("rect", (0, 100, 60, 110), 0)  # starts at the image border
    cleaned = clean_mask(_mask(("rect", (0, 60, 300, 260), 255), notch))

    assert _at(cleaned, 30, 105) < 50


def test_empty_mask_stays_empty():
    cleaned = clean_mask(Image.new("L", SIZE, 0))

    assert cleaned.size == SIZE
    assert np.array(cleaned).max() == 0


def test_edge_is_softened_but_never_grows_outwards():
    cleaned = clean_mask(_mask(("rect", (100, 60, 300, 260), 255)))
    values = np.array(cleaned)

    assert 0 < _at(cleaned, 100, 160) < 255  # soft edge
    assert values[:, :95].max() == 0  # nothing spreads out of the person
    assert values[:55, :].max() == 0


def test_remove_with_cleanup_uses_the_cleaned_mask():
    mask = _mask(("rect", (100, 60, 300, 260), 255), ("rect", (20, 20, 28, 28), 255))
    session = SimpleNamespace(predict=lambda *_args, **_kwargs: mask)
    img = Image.new("RGB", SIZE, (200, 50, 50))

    plain = remove(img.copy(), session=session)
    cleaned = remove(img.copy(), session=session, cleanup=True)

    assert plain.getpixel((24, 24))[3] == 255  # speck stays without cleanup
    assert cleaned.getpixel((24, 24))[3] == 0
    assert cleaned.getpixel((200, 160))[3] == 255


def test_cache_key_depends_on_model_and_cleanup():
    img = Image.new("RGB", (32, 32), (10, 20, 30))

    keys = {
        RemovebgStep("modnet", True).hash_image_fast(img),
        RemovebgStep("modnet", False).hash_image_fast(img),
        RemovebgStep("u2netp", True).hash_image_fast(img),
    }

    assert len(keys) == 3
    assert RemovebgStep("modnet", True).hash_image_fast(img) == RemovebgStep("modnet", True).hash_image_fast(img)


@pytest.mark.parametrize("enabled", [True, False])
def test_pipeline_passes_the_setting_to_the_step(tmp_path: Path, enabled: bool):
    calls: list[tuple] = []

    class Spy(PipelineStep):
        def __init__(self, model_name, cleanup):
            calls.append((model_name, cleanup))

        def __call__(self, context, next_step):
            next_step(context)

    image_file = tmp_path / "in.jpg"
    Image.new("RGB", (64, 48), (1, 2, 3)).save(image_file)

    with (
        patch.object(processes, "RemovebgStep", Spy),
        patch.object(appconfig.mediaprocessing, "remove_background_cleanup", enabled),
    ):
        processes.process_image_inner(image_file, SingleImageProcessing(remove_background=True), preview=False)

    assert calls == [(appconfig.mediaprocessing.remove_background_model, enabled)]
