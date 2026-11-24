"""Dark design for the photo strip ("Tira 2 fotos"): night background with a few stars and a thin gold frame
with the message.

Two PNGs are generated into userdata/strip/ and used by the strip collage action:
  - a background (drawn behind the photos)
  - a transparent frame (drawn on top: gold border, outlines around the photos, a divider and the message)

The message is drawn here instead of with the app's text element, because the font has no glyphs for symbols like
the heart. Hearts (♥ ♡) and stars (★) are drawn as shapes, so they look the same on every PC.

The frame is regenerated whenever the app config is saved (see sync_with_config), so the strip follows the event phrase.
"""

import logging
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import USERDATA_PATH

logger = logging.getLogger(__name__)

STRIP_NAME = "Tira 2 fotos"
OUT_DIR = Path(USERDATA_PATH, "strip")
BACKGROUND_FILE = "strip_dark_background.png"
FRAME_FILE = "strip_dark_frame.png"
FONT_FILE = Path(__file__).resolve().parents[1] / "demoassets" / "userdata" / "fonts" / "Roboto-Bold.ttf"

CANVAS_WIDTH = 600
CANVAS_HEIGHT = 1800
PHOTO_WIDTH = 520
PHOTO_HEIGHT = 600
PHOTO_X = (CANVAS_WIDTH - PHOTO_WIDTH) // 2
PHOTO_1_Y = 90
PHOTO_2_Y = PHOTO_1_Y + PHOTO_HEIGHT + 40
PHOTO_RECTS = [(PHOTO_X, PHOTO_1_Y, PHOTO_WIDTH, PHOTO_HEIGHT), (PHOTO_X, PHOTO_2_Y, PHOTO_WIDTH, PHOTO_HEIGHT)]
DIVIDER_Y = PHOTO_2_Y + PHOTO_HEIGHT + 120
MESSAGE_BASELINE_Y = DIVIDER_Y + 110

GOLD = (201, 162, 75)
TEXT_COLOR = "#F5E6B8"  # warm light gold, readable on the dark background
FALLBACK_BACKGROUND = "#0b0b14"
SYMBOLS = "♥♡★"
MAX_FONT_SIZE = 60
MARGIN = 44


def make_background(size: tuple[int, int] = (CANVAS_WIDTH, CANVAS_HEIGHT)) -> Image.Image:
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
    for _ in range(140):
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


def make_frame(message: str, text_color: str = TEXT_COLOR) -> Image.Image:
    size = (CANVAS_WIDTH, CANVAS_HEIGHT)
    frame = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    draw.rectangle([16, 16, CANVAS_WIDTH - 17, CANVAS_HEIGHT - 17], outline=GOLD + (255,), width=3)
    draw.rectangle([28, 28, CANVAS_WIDTH - 29, CANVAS_HEIGHT - 29], outline=GOLD + (110,), width=1)

    for x, y, w, h in PHOTO_RECTS:  # just outside the photo so nothing of the picture is covered
        draw.rectangle([x - 4, y - 4, x + w + 3, y + h + 3], outline=GOLD + (255,), width=3)

    cx = CANVAS_WIDTH // 2
    draw.line([(60, DIVIDER_Y), (cx - 18, DIVIDER_Y)], fill=GOLD + (255,), width=2)
    draw.line([(cx + 18, DIVIDER_Y), (CANVAS_WIDTH - 60, DIVIDER_Y)], fill=GOLD + (255,), width=2)
    draw.polygon([(cx, DIVIDER_Y - 9), (cx + 9, DIVIDER_Y), (cx, DIVIDER_Y + 9), (cx - 9, DIVIDER_Y)], fill=GOLD + (255,))

    rgb = tuple(int(text_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    draw_message(draw, message, CANVAS_WIDTH, MESSAGE_BASELINE_Y, rgb + (255,), MAX_FONT_SIZE, MARGIN)

    return frame


def render(message: str, text_color: str = TEXT_COLOR, out_dir: Path = OUT_DIR) -> tuple[str, str]:
    """Writes the background and the frame with the message, returns their paths (posix, as the config wants them)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    background, frame = out_dir / BACKGROUND_FILE, out_dir / FRAME_FILE
    make_background().save(background)
    make_frame(message, text_color).save(frame)
    return background.as_posix(), frame.as_posix()


def strip_message(config) -> str:
    """The text on the strip: the text typed for the strip, or the event phrase if none was typed."""
    return (config.uisettings.STRIP_TEXT or config.uisettings.FRONTPAGE_TITLE or "").strip()


def sync_with_config(config) -> bool:
    """Regenerates the strip frame so it shows the current text. Does nothing if there is no strip action using the
    generated frame or no text yet. Returns True if the frame was written."""
    message = strip_message(config)
    if not message:
        return False

    uses_generated_frame = any(
        action.name == STRIP_NAME
        and action.processing.canvas_img_front_file is not None
        and Path(action.processing.canvas_img_front_file).name == FRAME_FILE
        for action in config.actions.collage
    )
    if not uses_generated_frame:
        return False

    render(message)
    logger.info(f"strip frame regenerated with the text: {message!r}")
    return True
