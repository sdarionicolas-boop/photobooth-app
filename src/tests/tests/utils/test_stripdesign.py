import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.container import container
from photobooth.utils import stripdesign


def _config(
    title: str = "", strip_text: str = "", frame: str | None = f"userdata/strip/{stripdesign.FRAME_FILE}", name: str = stripdesign.STRIP_NAME
):
    action = SimpleNamespace(name=name, processing=SimpleNamespace(canvas_img_front_file=Path(frame) if frame else None))
    return SimpleNamespace(
        uisettings=SimpleNamespace(FRONTPAGE_TITLE=title, STRIP_TEXT=strip_text),
        actions=SimpleNamespace(collage=[SimpleNamespace(name="default action", processing=SimpleNamespace(canvas_img_front_file=None)), action]),
    )


def _digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_render_writes_background_and_frame(tmp_path: Path):
    background, frame = stripdesign.render("MIS XV LUCIA♥", out_dir=tmp_path)

    with Image.open(background) as bg:
        assert bg.size == (stripdesign.CANVAS_WIDTH, stripdesign.CANVAS_HEIGHT)
        assert bg.mode == "RGB"
    with Image.open(frame) as fr:
        assert fr.size == (stripdesign.CANVAS_WIDTH, stripdesign.CANVAS_HEIGHT)
        assert fr.mode == "RGBA"
        assert fr.getchannel("A").getbbox() is not None  # something is drawn
        # the photo areas stay see-through so the pictures are visible
        x, y, w, h = stripdesign.PHOTO_RECTS[0]
        assert fr.getpixel((x + w // 2, y + h // 2))[3] == 0


def test_frame_follows_the_message(tmp_path: Path):
    _, frame_a = stripdesign.render("MI BODA", out_dir=tmp_path / "a")
    _, frame_b = stripdesign.render("MIS XV LUCIA", out_dir=tmp_path / "b")
    _, frame_a_again = stripdesign.render("MI BODA", out_dir=tmp_path / "c")

    assert _digest(frame_a) != _digest(frame_b)
    assert _digest(frame_a) == _digest(frame_a_again)  # deterministic


@pytest.mark.parametrize("message", ["♥", "♡ ★ ♥", "A" * 80, "ÁÉÍÓÚ ¡Ñandú!"])
def test_render_handles_symbols_and_long_messages(tmp_path: Path, message: str):
    _, frame = stripdesign.render(message, out_dir=tmp_path)

    with Image.open(frame) as fr:
        assert fr.size == (stripdesign.CANVAS_WIDTH, stripdesign.CANVAS_HEIGHT)


def test_sync_uses_strip_text_before_title():
    with patch.object(stripdesign, "render") as render:
        assert stripdesign.sync_with_config(_config(title="MI BODA", strip_text="Gracias por venir")) is True

        render.assert_called_once_with("Gracias por venir")


def test_sync_falls_back_to_the_event_title():
    with patch.object(stripdesign, "render") as render:
        assert stripdesign.sync_with_config(_config(title="  MIS XV LUCIA♥  ")) is True

        render.assert_called_once_with("MIS XV LUCIA♥")


@pytest.mark.parametrize(
    "config",
    [
        _config(),  # nothing typed yet
        _config(title="MI BODA", frame=None),  # strip without the generated frame: user made their own design
        _config(title="MI BODA", frame="userdata/own/other_frame.png"),
        _config(title="MI BODA", name="Otra tira"),
    ],
)
def test_sync_leaves_other_setups_alone(config):
    with patch.object(stripdesign, "render") as render:
        assert stripdesign.sync_with_config(config) is False

        render.assert_not_called()


def test_saving_the_app_config_redraws_the_strip(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist") as persist,
        patch.object(stripdesign, "sync_with_config") as sync,
    ):
        response = client_authenticated.patch("/admin/config/app", json={})

        assert response.status_code == 200
        persist.assert_called_once()
        sync.assert_called_once()


def test_saving_a_plugin_config_does_not_redraw_the_strip(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist"),
        patch.object(stripdesign, "sync_with_config") as sync,
    ):
        response = client_authenticated.patch("/admin/config/photobooth.plugins.synchronizer.synchronizer", json={})

        assert response.status_code == 200
        sync.assert_not_called()


def test_strip_design_error_does_not_fail_the_save(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist"),
        patch.object(stripdesign, "sync_with_config", side_effect=RuntimeError("disk full")),
    ):
        response = client_authenticated.patch("/admin/config/app", json={})

        assert response.status_code == 200
