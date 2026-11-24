import logging
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth import USERDATA_PATH
from photobooth.container import container

logger = logging.getLogger(name=None)


@pytest.fixture()
def background_file() -> Generator[str, None, None]:
    """a temporary background in userdata/backgrounds, removed after the test"""
    folder = Path(USERDATA_PATH, "backgrounds")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"test_background_{uuid4().hex}.png"
    Image.new("RGB", (200, 133), (10, 200, 30)).save(path)
    try:
        yield path.as_posix()
    finally:
        path.unlink(missing_ok=True)


def test_list_backgrounds(client: TestClient, background_file: str):
    response = client.get("/background/")

    assert response.status_code == 200
    entries = response.json()
    match = [e for e in entries if e["file"] == background_file]
    assert len(match) == 1
    assert match[0]["url"].startswith("/userdata/backgrounds/")


def test_apply_background(client: TestClient, background_file: str):
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.patch(f"/background/{mediaitem.id}", params={"file": background_file})

    assert response.status_code == 200
    updated = container.mediacollection_service.get_item(mediaitem.id)
    assert updated.pipeline_config["img_background_enable"] is True
    assert updated.pipeline_config["remove_background"] is True
    assert Path(updated.pipeline_config["img_background_file"]).name == Path(background_file).name
    assert updated.revision > mediaitem.revision


def test_apply_no_background(client: TestClient):
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.patch(f"/background/{mediaitem.id}")

    assert response.status_code == 200
    updated = container.mediacollection_service.get_item(mediaitem.id)
    assert updated.pipeline_config["img_background_enable"] is False
    assert updated.pipeline_config["remove_background"] is False


def test_apply_background_not_listed(client: TestClient):
    """arbitrary files must not be accepted"""
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.patch(f"/background/{mediaitem.id}", params={"file": "pyproject.toml"})

    assert response.status_code == 406


def test_apply_background_unknown_item(client: TestClient):
    response = client.patch(f"/background/{uuid4()}")

    assert response.status_code == 404
