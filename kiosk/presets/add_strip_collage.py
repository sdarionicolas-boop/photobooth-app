"""Adds (or replaces) a "Tira 2 fotos" collage action: a 600x1800 photo strip with two photos and a message.

Run from the repository root while the app is NOT running (the app rewrites the config on save), then start the app:

    uv run python kiosk/presets/add_strip_collage.py --message "¡Nuestra Gran Fiesta!"

The strip is dark (night background with a thin gold frame and the message, generated into userdata/strip/).
Every run replaces the action with the same name, so it can be repeated to change the message or colors.
A backup of config/config.json is written next to it first.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from photobooth.services.config.groups.actions import CollageConfigurationSet  # noqa: E402
from photobooth.utils import framedesign  # noqa: E402

CONFIG_FILE = Path("config/config.json")
STRIP_NAME = framedesign.STRIP_NAME


def design_assets(message: str, text_color: str) -> dict[str, str]:
    """Generates the dark frames with the message and today's date, returns their paths by name."""
    return framedesign.render(message, text_color)


def build_action(name: str, background: str, background_image: str | None = None, frame_image: str | None = None) -> dict:
    return {
        "name": name,
        "jobcontrol": {
            "countdown_capture": 10.0,
            "countdown_capture_second_following": 10.0,
            "ask_approval_each_capture": False,
            "show_individual_captures_in_gallery": False,
        },
        "processing": {
            "canvas_width": framedesign.STRIP_SIZE[0],
            "canvas_height": framedesign.STRIP_SIZE[1],
            "merge_definition": [
                {
                    "description": "photo 1",
                    "pos_x": framedesign.STRIP_PHOTO_X,
                    "pos_y": framedesign.STRIP_PHOTO_1_Y,
                    "width": framedesign.STRIP_PHOTO_W,
                    "height": framedesign.STRIP_PHOTO_H,
                },
                {
                    "description": "photo 2",
                    "pos_x": framedesign.STRIP_PHOTO_X,
                    "pos_y": framedesign.STRIP_PHOTO_2_Y,
                    "width": framedesign.STRIP_PHOTO_W,
                    "height": framedesign.STRIP_PHOTO_H,
                },
            ],
            "canvas_fill_background_enable": True,
            "canvas_fill_background_color": background,
            "canvas_img_background_enable": bool(background_image),
            "canvas_img_background_file": background_image,
            "canvas_img_front_enable": bool(frame_image),
            "canvas_img_front_file": frame_image,
            "canvas_elements_enable": False,  # the message is part of the frame image
            "canvas_elements": [],
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
    parser.add_argument("--background", default=framedesign.FALLBACK_BACKGROUND, help="strip background color (under the night image)")
    parser.add_argument("--text-color", default=framedesign.TEXT_COLOR, help="message color")
    parser.add_argument("--name", default="Tira 2 fotos", help="name of the action")
    args = parser.parse_args()

    if not CONFIG_FILE.is_file():
        print(f"{CONFIG_FILE} not found. Run this from the repository root, after the app ran once.", file=sys.stderr)
        return 1
    paths = design_assets(args.message, args.text_color)
    action = build_action(args.name, args.background, paths["strip_background"], paths["strip_frame"])
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
