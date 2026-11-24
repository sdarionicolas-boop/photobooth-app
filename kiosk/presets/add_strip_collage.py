"""Adds (or replaces) a "Tira 2 fotos" collage action: a 600x1800 photo strip with two photos and a message.

Run from the repository root while the app is NOT running (the app rewrites the config on save), then start the app:

    uv run python kiosk/presets/add_strip_collage.py --message "¡Nuestra Gran Fiesta!"

Every run replaces the action with the same name, so it can be repeated to change the message or colors.
A backup of config/config.json is written next to it first.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import ImageFont

from photobooth.services.config.groups.actions import CollageConfigurationSet

CONFIG_FILE = Path("config/config.json")
FONT_FILE = Path("userdata/demoassets/fonts/Roboto-Bold.ttf")

CANVAS_WIDTH = 600
CANVAS_HEIGHT = 1800
PHOTO_WIDTH = 520
PHOTO_HEIGHT = 600
PHOTO_X = (CANVAS_WIDTH - PHOTO_WIDTH) // 2
PHOTO_1_Y = 70
PHOTO_2_Y = PHOTO_1_Y + PHOTO_HEIGHT + 40
MESSAGE_Y = PHOTO_2_Y + PHOTO_HEIGHT + 120
MARGIN = 40


def fit_message(message: str, max_font_size: int) -> tuple[int, int]:
    """Largest font size (<= max) at which the message fits the strip, and the x position that centers it."""
    size = max_font_size
    while size > 14:
        width = ImageFont.truetype(str(FONT_FILE), size).getlength(message)
        if width <= CANVAS_WIDTH - 2 * MARGIN:
            return size, round((CANVAS_WIDTH - width) / 2)
        size -= 2
    width = ImageFont.truetype(str(FONT_FILE), size).getlength(message)
    return size, max(0, round((CANVAS_WIDTH - width) / 2))


def build_action(name: str, message: str, background: str, text_color: str, font_size: int) -> dict:
    size, pos_x = fit_message(message, font_size)

    return {
        "name": name,
        "jobcontrol": {
            "countdown_capture": 3.0,
            "countdown_capture_second_following": 3.0,
            "ask_approval_each_capture": False,
            "show_individual_captures_in_gallery": False,
        },
        "processing": {
            "canvas_width": CANVAS_WIDTH,
            "canvas_height": CANVAS_HEIGHT,
            "merge_definition": [
                {"description": "photo 1", "pos_x": PHOTO_X, "pos_y": PHOTO_1_Y, "width": PHOTO_WIDTH, "height": PHOTO_HEIGHT},
                {"description": "photo 2", "pos_x": PHOTO_X, "pos_y": PHOTO_2_Y, "width": PHOTO_WIDTH, "height": PHOTO_HEIGHT},
            ],
            "canvas_fill_background_enable": True,
            "canvas_fill_background_color": background,
            "canvas_elements_enable": True,
            "canvas_elements": [
                {
                    "type": "text",
                    "text": message,
                    "pos_x": pos_x,
                    "pos_y": MESSAGE_Y,
                    "font_size": size,
                    "font": FONT_FILE.as_posix(),
                    "color": text_color,
                }
            ],
        },
        "trigger": {
            "ui_trigger": {"show_button": True, "title": "Tira", "icon": "view_agenda"},
            "keyboard_trigger": {"keycode": ""},
            "gpio_trigger": {"pin": "", "trigger_on": "pressed"},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--message", default="¡Nuestra Gran Fiesta!", help="text printed under the photos")
    parser.add_argument("--background", default="#FFFFFF", help="strip background color")
    parser.add_argument("--text-color", default="#0f172a", help="message color")
    parser.add_argument("--font-size", type=int, default=56, help="largest font size, shrinks for long messages")
    parser.add_argument("--name", default="Tira 2 fotos", help="name of the action")
    args = parser.parse_args()

    if not CONFIG_FILE.is_file():
        print(f"{CONFIG_FILE} not found. Run this from the repository root, after the app ran once.", file=sys.stderr)
        return 1
    if not FONT_FILE.is_file():
        print(f"{FONT_FILE} not found. Start the app once so the demo assets are linked.", file=sys.stderr)
        return 1

    action = build_action(args.name, args.message, args.background, args.text_color, args.font_size)
    CollageConfigurationSet.model_validate(action)  # fail here, not when the app loads the config

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    collages = config["actions"]["collage"]
    replaced = [i for i, a in enumerate(collages) if a.get("name") == args.name]

    backup = CONFIG_FILE.with_name(f"{CONFIG_FILE.name}_backup-strip-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(CONFIG_FILE, backup)

    if replaced:
        collages[replaced[0]] = action
    else:
        collages.append(action)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{'replaced' if replaced else 'added'} collage action '{args.name}' (index {replaced[0] if replaced else len(collages) - 1})")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
