import io
import logging
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from photobooth.container import container

from ...util import is_same

logger = logging.getLogger(name=None)


def _signature_png(size: tuple[int, int]) -> bytes:
    """transparent canvas with an opaque red box, like a stroke drawn by the user"""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(size[0] // 4, size[0] // 2):
        for y in range(size[1] // 4, size[1] // 2):
            img.putpixel((x, y), (255, 0, 0, 255))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def test_apply_signature(client: TestClient):
    mediaitem = container.mediacollection_service.get_item_latest()

    with Image.open(mediaitem.processed) as before:
        before.load()
        size = before.size

    response = client.post(f"/signature/{mediaitem.id}", content=_signature_png(size), headers={"Content-Type": "image/png"})

    assert response.status_code == 200

    with Image.open(mediaitem.processed) as after:
        after.load()
        assert after.size == size
        if is_same(before, after):
            raise AssertionError("img data before and after same. signature was not applied!")
        # center of the drawn box must be (jpeg-tolerant) red
        r, g, b = after.convert("RGB").getpixel((size[0] * 3 // 8, size[1] * 3 // 8))
        assert r > 200 and g < 60 and b < 60


def test_apply_signature_bumps_revision(client: TestClient):
    """clients bust their cache by revision, so it must change when the picture changes"""
    mediaitem = container.mediacollection_service.get_item_latest()
    revision_before = mediaitem.revision

    with Image.open(mediaitem.processed) as before:
        size = before.size

    response = client.post(f"/signature/{mediaitem.id}", content=_signature_png(size), headers={"Content-Type": "image/png"})

    assert response.status_code == 200
    assert container.mediacollection_service.get_item(mediaitem.id).revision > revision_before


def test_apply_signature_scales_to_image(client: TestClient):
    mediaitem = container.mediacollection_service.get_item_latest()

    with Image.open(mediaitem.processed) as before:
        size = before.size

    # signature canvas of different size than the picture (as drawn on screen) is scaled to fit
    response = client.post(
        f"/signature/{mediaitem.id}",
        content=_signature_png((size[0] // 4, size[1] // 4)),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 200

    with Image.open(mediaitem.processed) as after:
        assert after.size == size


def test_apply_signature_invalid_image(client: TestClient):
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.post(f"/signature/{mediaitem.id}", content=b"not a png", headers={"Content-Type": "image/png"})

    assert response.status_code == 422


def test_apply_signature_unknown_item(client: TestClient):
    response = client.post(f"/signature/{uuid4()}", content=_signature_png((20, 20)), headers={"Content-Type": "image/png"})

    assert response.status_code == 404
