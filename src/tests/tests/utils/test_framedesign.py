import hashlib
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.container import container
from photobooth.services import processing as processing_module
from photobooth.utils import framedesign


def _config(
    title: str = "",
    strip_text: str = "",
    strip_frame: str | None = f"userdata/strip/{framedesign.STRIP_FRAME_FILE}",
    photo_frame: str | None = f"userdata/strip/{framedesign.PHOTO_FRAME_FILE}",
    strip_name: str = framedesign.STRIP_NAME,
):
    def collage(name, frame):
        return SimpleNamespace(name=name, processing=SimpleNamespace(canvas_img_front_file=Path(frame) if frame else None))

    def image(frame):
        overlay = SimpleNamespace(enable=frame is not None, image=Path(frame) if frame else None)
        return SimpleNamespace(processing=SimpleNamespace(img_frame=overlay))

    return SimpleNamespace(
        uisettings=SimpleNamespace(FRONTPAGE_TITLE=title, STRIP_TEXT=strip_text),
        actions=SimpleNamespace(
            image=[image(photo_frame)],
            collage=[collage("default action", None), collage(strip_name, strip_frame)],
        ),
    )


def _digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def _forget_last_render():
    framedesign._last_rendered = None
    yield
    framedesign._last_rendered = None


def test_today_is_day_month_year():
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", framedesign.today_text())


def test_render_writes_the_three_images(tmp_path: Path):
    paths = framedesign.render("MIS XV LUCIA♥", out_dir=tmp_path)

    assert set(paths) == {"photo_frame", "strip_background", "strip_frame"}

    with Image.open(paths["strip_background"]) as bg:
        assert bg.size == framedesign.STRIP_SIZE
    with Image.open(paths["strip_frame"]) as strip:
        assert strip.size == framedesign.STRIP_SIZE
        x, y, w, h = framedesign.STRIP_PHOTO_RECTS[0]
        assert strip.getpixel((x + w // 2, y + h // 2))[3] == 0  # the photos are seen through the frame
    with Image.open(paths["photo_frame"]) as photo:
        assert photo.size == framedesign.PHOTO_SIZE
        alpha = photo.getchannel("A")
        x, y, w, h = framedesign.PHOTO_WINDOW
        assert alpha.point(lambda v: 255 if v < 255 else 0).getbbox() == (x, y, x + w, y + h)  # one window, where the photo goes
        assert alpha.getpixel((5, 5)) == 255  # the rest is opaque


def test_frames_follow_the_phrase_and_the_date(tmp_path: Path):
    base = framedesign.render("MI BODA", date="24/11/2026", out_dir=tmp_path / "a")
    other_phrase = framedesign.render("MIS XV LUCIA", date="24/11/2026", out_dir=tmp_path / "b")
    other_day = framedesign.render("MI BODA", date="25/11/2026", out_dir=tmp_path / "c")
    same = framedesign.render("MI BODA", date="24/11/2026", out_dir=tmp_path / "d")

    for name in ("photo_frame", "strip_frame"):
        assert _digest(base[name]) != _digest(other_phrase[name])
        assert _digest(base[name]) != _digest(other_day[name])  # the date is on the picture
        assert _digest(base[name]) == _digest(same[name])  # deterministic


@pytest.mark.parametrize("message", ["♥", "♡ ★ ♥", "A" * 80, "ÁÉÍÓÚ ¡Ñandú!"])
def test_render_handles_symbols_and_long_messages(tmp_path: Path, message: str):
    paths = framedesign.render(message, out_dir=tmp_path)

    with Image.open(paths["photo_frame"]) as photo:
        assert photo.size == framedesign.PHOTO_SIZE


def test_sync_uses_the_picture_text_before_the_title():
    with patch.object(framedesign, "render") as render:
        assert framedesign.sync_with_config(_config(title="MI BODA", strip_text="Gracias por venir")) is True

        assert render.call_args.args == ("Gracias por venir",)


def test_sync_falls_back_to_the_event_title():
    with patch.object(framedesign, "render") as render:
        assert framedesign.sync_with_config(_config(title="  MIS XV LUCIA♥  ")) is True

        assert render.call_args.args == ("MIS XV LUCIA♥",)


def test_sync_works_with_only_the_photo_or_only_the_strip():
    with patch.object(framedesign, "render") as render:
        assert framedesign.sync_with_config(_config(title="MI BODA", strip_frame=None)) is True
        assert framedesign.sync_with_config(_config(title="MI BODA", photo_frame=None)) is True

        assert render.call_count == 2


@pytest.mark.parametrize(
    "config",
    [
        _config(),  # nothing typed yet
        _config(title="MI BODA", strip_frame=None, photo_frame=None),  # own designs, nothing generated is used
        _config(title="MI BODA", strip_frame="userdata/own/other.png", photo_frame="userdata/own/other.png"),
        _config(title="MI BODA", strip_name="Otra tira", photo_frame=None),
    ],
)
def test_sync_leaves_other_setups_alone(config):
    with patch.object(framedesign, "render") as render:
        assert framedesign.sync_with_config(config) is False

        render.assert_not_called()


def test_before_a_capture_frames_are_only_redrawn_when_needed(tmp_path: Path):
    (tmp_path / framedesign.PHOTO_FRAME_FILE).write_bytes(b"x")
    (tmp_path / framedesign.STRIP_FRAME_FILE).write_bytes(b"x")
    config = _config(title="MI BODA")

    with patch.object(framedesign, "OUT_DIR", tmp_path), patch.object(framedesign, "render") as render:
        assert framedesign.sync_with_config(config, only_if_changed=True) is True  # first time
        assert framedesign.sync_with_config(config, only_if_changed=True) is False  # nothing changed

        with patch.object(framedesign, "today_text", return_value="01/01/2099"):
            assert framedesign.sync_with_config(config, only_if_changed=True) is True  # a new day: the date must change

        config.uisettings.FRONTPAGE_TITLE = "OTRA FRASE"
        with patch.object(framedesign, "today_text", return_value="01/01/2099"):
            assert framedesign.sync_with_config(config, only_if_changed=True) is True  # new phrase

        assert render.call_count == 3


def test_a_missing_frame_file_is_drawn_again(tmp_path: Path):
    config = _config(title="MI BODA")

    with patch.object(framedesign, "OUT_DIR", tmp_path), patch.object(framedesign, "render") as render:
        framedesign.sync_with_config(config, only_if_changed=True)
        assert framedesign.sync_with_config(config, only_if_changed=True) is True  # files were never written: draw again

        assert render.call_count == 2


def test_saving_the_app_config_redraws_the_frames(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist") as persist,
        patch.object(framedesign, "sync_with_config") as sync,
    ):
        response = client_authenticated.patch("/admin/config/app", json={})

        assert response.status_code == 200
        persist.assert_called_once()
        sync.assert_called_once()


def test_saving_a_plugin_config_does_not_redraw_the_frames(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist"),
        patch.object(framedesign, "sync_with_config") as sync,
    ):
        response = client_authenticated.patch("/admin/config/photobooth.plugins.synchronizer.synchronizer", json={})

        assert response.status_code == 200
        sync.assert_not_called()


def test_a_frame_error_does_not_fail_the_save(client_authenticated: TestClient):
    with (
        patch.object(container.config_service, "validate_and_set_current_and_persist"),
        patch.object(framedesign, "sync_with_config", side_effect=RuntimeError("disk full")),
    ):
        response = client_authenticated.patch("/admin/config/app", json={})

        assert response.status_code == 200


def test_a_capture_redraws_the_frames_and_survives_errors():
    service = container.processing_service
    before = (service._workflow_jobmodel, service._process_thread)

    try:
        with (
            patch.object(framedesign, "sync_with_config", side_effect=RuntimeError("disk full")) as sync,
            patch.dict(processing_module.ACTION_TO_MODEL, {"image": MagicMock(return_value=MagicMock())}),
            patch.object(processing_module, "Thread") as thread,
            patch.object(service, "_check_occupied"),
            patch.object(service._information_service, "stats_counter_increment"),
        ):
            service.trigger_action("image", 0)  # must not raise

            sync.assert_called_once_with(appconfig, only_if_changed=True)
            thread.return_value.start.assert_called_once()
    finally:
        service._workflow_jobmodel, service._process_thread = before
