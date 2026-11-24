"""Sets the frontpage (first screen) to an event title with today's date below, e.g. "MIS XV LUCIA♥" / "24/11/2026".

Run from the repository root while the app is NOT running (the app rewrites the config on save), then start the app:

    uv run python kiosk/presets/set_frontpage_title.py --title "MIS XV LUCIA♥"

The date is filled in by the frontend (always today). A backup of config/config.json is written first.
"""

import argparse
import html
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path("config/config.json")


def build_html(title: str, show_date: bool, title_size: str, date_size: str) -> str:
    date_html = f'<div style="font-size:{date_size};letter-spacing:0.2em;margin-top:1.5rem;opacity:0.9">{{date}}</div>' if show_date else ""
    return (
        '<div class="fixed-center text-center text-white" style="width:92vw;text-shadow:0 0 24px rgba(255,255,255,0.6)">'
        f'<div style="font-size:{title_size};font-weight:800;line-height:1.1">{html.escape(title)}</div>'
        f"{date_html}"
        "</div>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--title", required=True, help="event title shown big on the first screen")
    parser.add_argument("--no-date", action="store_true", help="do not show the date below the title")
    parser.add_argument("--title-size", default="clamp(2.5rem, 10vw, 7rem)", help="css font size of the title")
    parser.add_argument("--date-size", default="clamp(1.5rem, 5vw, 3.5rem)", help="css font size of the date")
    args = parser.parse_args()

    if not CONFIG_FILE.is_file():
        print(f"{CONFIG_FILE} not found. Run this from the repository root, after the app ran once.", file=sys.stderr)
        return 1

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    backup = CONFIG_FILE.with_name(f"{CONFIG_FILE.name}_backup-title-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(CONFIG_FILE, backup)

    config["uisettings"]["FRONTPAGE_TEXT"] = build_html(args.title, not args.no_date, args.title_size, args.date_size)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"frontpage text set to '{args.title}'{'' if args.no_date else ' + date'}")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
