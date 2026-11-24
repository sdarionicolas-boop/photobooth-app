"""Dark frames for the pictures: night background with a few stars and a thin gold frame that always carries the event
phrase and today's date.

Generated into userdata/strip/ and used by the actions:
  - photo ("Foto"): one PNG, the frame of the picture. The photo is seen through its transparent window.
  - strip ("Tira 2 fotos"): a background (drawn behind the photos) and a frame (drawn on top)

The phrase and the date are drawn here instead of with the app's text elements: the font has no glyphs for symbols like
the heart (hearts ♥ ♡ and stars ★ are drawn as shapes) and the date has to be the one of the day of the picture.
The frames are redrawn when the app config is saved and before every capture if the phrase or the day changed.
"""

import logging
import math
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import USERDATA_PATH

logger = logging.getLogger(__name__)

STRIP_NAME = "Tira 2 fotos"
OUT_DIR = Path(USERDATA_PATH, "strip")
STRIP_BACKGROUND_FILE = "strip_dark_background.png"
STRIP_FRAME_FILE = "strip_dark_frame.png"
PHOTO_FRAME_FILE = "photo_dark_frame.png"
FONT_FILE = Path(__file__).resolve().parents[1] / "demoassets" / "userdata" / "fonts" / "Roboto-Bold.ttf"

GOLD = (201, 162, 75)
TEXT_COLOR = "#F5E6B8"  # warm light gold, readable on the dark background
FALLBACK_BACKGROUND = "#0b0b14"
SYMBOLS = "♥♡★"
MARGIN = 44

# strip: 600x1800, two photos on top of each other
STRIP_SIZE = (600, 1800)
STRIP_PHOTO_W, STRIP_PHOTO_H = 520, 600
STRIP_PHOTO_X = (STRIP_SIZE[0] - STRIP_PHOTO_W) // 2
STRIP_PHOTO_1_Y = 90
STRIP_PHOTO_2_Y = STRIP_PHOTO_1_Y + STRIP_PHOTO_H + 40
STRIP_PHOTO_RECTS = [
    (STRIP_PHOTO_X, STRIP_PHOTO_1_Y, STRIP_PHOTO_W, STRIP_PHOTO_H),
    (STRIP_PHOTO_X, STRIP_PHOTO_2_Y, STRIP_PHOTO_W, STRIP_PHOTO_H),
]
STRIP_DIVIDER_Y = STRIP_PHOTO_2_Y + STRIP_PHOTO_H + 100
STRIP_MESSAGE_BASELINE_Y = STRIP_DIVIDER_Y + 95
STRIP_DATE_BASELINE_Y = STRIP_MESSAGE_BASELINE_Y + 80

# photo: 800x1200 (2:3), one photo with the phrase and the date below
PHOTO_SIZE = (800, 1200)
PHOTO_WINDOW = (40, 60, 720, 800)  # x, y, width, height
PHOTO_DIVIDER_Y = PHOTO_WINDOW[1] + PHOTO_WINDOW[3] + 70
PHOTO_MESSAGE_BASELINE_Y = PHOTO_DIVIDER_Y + 100
PHOTO_DATE_BASELINE_Y = PHOTO_MESSAGE_BASELINE_Y + 75

MESSAGE_MAX_FONT = 62
DATE_FONT = 44


def today_text() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def make_background(size: tuple[int, int]) -> Image.Image:
    width, height = size
    top, middle = (6, 6, 12), (22, 16, 46)

    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        k = 1 - abs(2 * y / (height - 1) - 1)  # 0 at the top and bottom, 1 in the middle
        draw.line([(0, y), (width, y)], fill=tuple(round(top[i] + (middle[i] - top[i]) * k) for i in range(3)))

    stars = Image.new("RGBA", size, (0, 0, 0, 0))
    star_draw = ImageDraw.Draw(stars)
    rng = random.Random(42)  # same sky every time
    for _ in range(round(width * height / 7700)):
        x, y = rng.randrange(width), rng.randrange(height)
        r = rng.choice([1, 1, 1, 2])
        star_draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rng.randrange(60, 200)))

    return Image.alpha_composite(image.convert("RGBA"), stars).convert("RGB")


def _heart_points(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    points = []
    for degrees in range(0, 360, 4):
        t = math.radians(degrees)
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        points.append((cx + x * size / 34, cy + y * size / 34))
    return points


def _star_points(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    outer, inner = size * 0.5, size * 0.22
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / 5 * i - math.pi / 2
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _draw_symbol(draw: ImageDraw.ImageDraw, symbol: str, cx: float, cy: float, size: float, color: tuple) -> None:
    if symbol == "★":
        draw.polygon(_star_points(cx, cy, size), fill=color)
    elif symbol == "♡":
        draw.polygon(_heart_points(cx, cy, size), outline=color, width=max(2, round(size / 14)))
    else:
        draw.polygon(_heart_points(cx, cy, size), fill=color)


def draw_message(draw: ImageDraw.ImageDraw, message: str, canvas_width: int, baseline_y: int, color: tuple, max_size: int, margin: int) -> None:
    """Centered message in one line, shrinking until it fits. Symbols are drawn as shapes."""
    size = max_size
    while True:
        font = ImageFont.truetype(str(FONT_FILE), size)
        widths = [size * 0.95 if ch in SYMBOLS else font.getlength(ch) for ch in message]
        if sum(widths) <= canvas_width - 2 * margin or size <= 14:
            break
        size -= 2

    x = (canvas_width - sum(widths)) / 2
    for ch, width in zip(message, widths, strict=True):
        if ch in SYMBOLS:
            _draw_symbol(draw, ch, x + width / 2, baseline_y - size * 0.38, size * 0.85, color)
        else:
            draw.text((x, baseline_y), ch, font=font, fill=color, anchor="ls")
        x += width


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _draw_border_and_text(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    photo_rects: list[tuple[int, int, int, int]],
    divider_y: int,
    message: str,
    message_baseline_y: int,
    date_baseline_y: int,
    text_color: str,
    date: str,
) -> None:
    width, height = size
    draw.rectangle([16, 16, width - 17, height - 17], outline=GOLD + (255,), width=3)
    draw.rectangle([28, 28, width - 29, height - 29], outline=GOLD + (110,), width=1)

    for x, y, w, h in photo_rects:  # just outside the photo so nothing of the picture is covered
        draw.rectangle([x - 4, y - 4, x + w + 3, y + h + 3], outline=GOLD + (255,), width=3)

    cx = width // 2
    draw.line([(60, divider_y), (cx - 18, divider_y)], fill=GOLD + (255,), width=2)
    draw.line([(cx + 18, divider_y), (width - 60, divider_y)], fill=GOLD + (255,), width=2)
    draw.polygon([(cx, divider_y - 9), (cx + 9, divider_y), (cx, divider_y + 9), (cx - 9, divider_y)], fill=GOLD + (255,))

    color = _rgb(text_color) + (255,)
    draw_message(draw, message, width, message_baseline_y, color, MESSAGE_MAX_FONT, MARGIN)
    draw.text((width / 2, date_baseline_y), date, font=ImageFont.truetype(str(FONT_FILE), DATE_FONT), fill=color, anchor="ms")


def make_strip_frame(message: str, text_color: str = TEXT_COLOR, date: str | None = None) -> Image.Image:
    frame = Image.new("RGBA", STRIP_SIZE, (0, 0, 0, 0))
    _draw_border_and_text(
        ImageDraw.Draw(frame),
        STRIP_SIZE,
        STRIP_PHOTO_RECTS,
        STRIP_DIVIDER_Y,
        message,
        STRIP_MESSAGE_BASELINE_Y,
        STRIP_DATE_BASELINE_Y,
        text_color,
        date or today_text(),
    )
    return frame


def make_photo_frame(message: str, text_color: str = TEXT_COLOR, date: str | None = None) -> Image.Image:
    """Opaque frame with a transparent window: the app puts the captured picture into the window."""
    frame = make_background(PHOTO_SIZE).convert("RGBA")
    layer = Image.new("RGBA", PHOTO_SIZE, (0, 0, 0, 0))
    _draw_border_and_text(
        ImageDraw.Draw(layer),
        PHOTO_SIZE,
        [PHOTO_WINDOW],
        PHOTO_DIVIDER_Y,
        message,
        PHOTO_MESSAGE_BASELINE_Y,
        PHOTO_DATE_BASELINE_Y,
        text_color,
        date or today_text(),
    )
    frame = Image.alpha_composite(frame, layer)

    x, y, w, h = PHOTO_WINDOW
    frame.paste((0, 0, 0, 0), (x, y, x + w, y + h))  # the window, transparent
    return frame


def render(message: str, text_color: str = TEXT_COLOR, out_dir: Path = OUT_DIR, date: str | None = None) -> dict[str, str]:
    """Writes all the frames, returns their paths (posix, as the config wants them) by name:
    photo_frame, strip_background, strip_frame."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "photo_frame": out_dir / PHOTO_FRAME_FILE,
        "strip_background": out_dir / STRIP_BACKGROUND_FILE,
        "strip_frame": out_dir / STRIP_FRAME_FILE,
    }
    make_photo_frame(message, text_color, date).save(paths["photo_frame"])
    make_background(STRIP_SIZE).save(paths["strip_background"])
    make_strip_frame(message, text_color, date).save(paths["strip_frame"])
    return {name: path.as_posix() for name, path in paths.items()}


def picture_text(config) -> str:
    """The text on the pictures: the text typed for the pictures, or the event phrase if none was typed."""
    return (config.uisettings.STRIP_TEXT or config.uisettings.FRONTPAGE_TITLE or "").strip()


def uses_generated_frames(config) -> bool:
    photo = any(
        action.processing.img_frame.enable
        and action.processing.img_frame.image is not None
        and Path(action.processing.img_frame.image).name == PHOTO_FRAME_FILE
        for action in config.actions.image
    )
    strip = any(
        action.name == STRIP_NAME
        and action.processing.canvas_img_front_file is not None
        and Path(action.processing.canvas_img_front_file).name == STRIP_FRAME_FILE
        for action in config.actions.collage
    )
    return photo or strip


_last_rendered: tuple[str, str] | None = None


def sync_with_config(config, only_if_changed: bool = False) -> bool:
    """Redraws the frames with the current phrase and today's date. Does nothing if no action uses the generated
    frames or there is no phrase yet. With only_if_changed the frames are only redrawn when the phrase or the day changed
    since the last time (used before every capture). Returns True if the frames were written."""
    global _last_rendered

    message = picture_text(config)
    if not message or not uses_generated_frames(config):
        return False

    key = (message, today_text())
    if only_if_changed and key == _last_rendered and (OUT_DIR / PHOTO_FRAME_FILE).is_file() and (OUT_DIR / STRIP_FRAME_FILE).is_file():
        return False

    render(message, date=key[1])
    _last_rendered = key
    logger.info(f"picture frames redrawn: {message!r} {key[1]}")
    return True
