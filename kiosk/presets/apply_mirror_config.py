"""Configures the app as a magic mirror on a fresh machine (or re-applies it on an existing one).

Run from the repository root while the app is NOT running (the app rewrites the config on save):

    uv run python kiosk/presets/apply_mirror_config.py --title "MIS XV LUCIA♥"

What it sets:
  - webcam (PyAV, 1280x720 @ 25fps; auto-detected unless --camera is given)
  - only QR sharing: print/mail actions removed, QR code pointing to this PC's LAN IP
  - first screen: event title + today's date; no livestream while idle, no slideshow, no blurred background
  - a "Tira 2 fotos" collage action (2 photos + message)
  - optional admin password

Settings are merged into config/*.json (existing values stay), validated with the app's own models and
backed up before writing. Re-running is safe.

    --update-qr-ip   only refresh the QR link with the current LAN IP (used by start-kiosk.ps1 on every boot)
    --dry-run        show what would change, write nothing
"""

import argparse
import json
import shutil
import socket
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from add_strip_collage import build_action, design_assets  # noqa: E402

from photobooth.plugins.synchronizer.config import Common as SynchronizerCommon  # noqa: E402
from photobooth.services.config.groups.actions import GroupActions  # noqa: E402
from photobooth.services.config.groups.cameras import GroupCameras  # noqa: E402
from photobooth.services.config.groups.common import GroupCommon  # noqa: E402
from photobooth.services.config.groups.share import GroupShare  # noqa: E402
from photobooth.services.config.groups.uisettings import GroupUiSettings  # noqa: E402
from photobooth.utils import stripdesign  # noqa: E402
from photobooth.utils.enumerate import webcameras  # noqa: E402

PORT = 8000
STRIP_NAME = "Tira 2 fotos"


def detect_lan_ip() -> str | None:
    """IP of the interface used for the default route. Connecting a UDP socket sends no packets."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def qr_url(ip: str) -> str:
    return f"http://{ip}:{PORT}/sharepage/#?url=http://{ip}:{PORT}/media/full/{{identifier}}?rev={{revision}}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_json(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copy2(path, path.with_name(f"{path.name}_backup-mirror-{datetime.now():%Y%m%d-%H%M%S}"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def choose_camera(requested: str) -> str:
    if requested != "auto":
        return requested

    found = webcameras()
    if not found:
        raise SystemExit("No webcam detected. Connect it, or pass its exact name with --camera.")
    if len(found) > 1:
        print(f"Several webcams found: {found}. Using the first one; pass --camera to choose another.")
    return found[0]


def guest_buttons(actions: dict) -> None:
    """Only two buttons for the guest: "Foto" (first single image action) and "Tira" (the strip)."""
    for action_type, items in actions.items():
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            ui = item.get("trigger", {}).get("ui_trigger")
            if ui is None:
                continue
            is_photo = action_type == "image" and index == 0
            is_strip = action_type == "collage" and item.get("name") == STRIP_NAME
            ui["show_button"] = is_photo or is_strip
            if is_photo:
                ui["title"], ui["icon"] = "Foto", "photo_camera"
                item.setdefault("jobcontrol", {})["countdown_capture"] = 10.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--title", help="event title for the first screen, e.g. 'MIS XV LUCIA♥'")
    parser.add_argument("--camera", default="auto", help="exact webcam name (default: first detected)")
    parser.add_argument("--resolution", default="1280x720", help="webcam capture size, default 1280x720")
    parser.add_argument("--framerate", type=int, default=25)
    parser.add_argument("--ip", default="auto", help="LAN IP used in the QR link (default: detected)")
    parser.add_argument("--admin-password", help="admin password (min 4 characters); unchanged if omitted")
    parser.add_argument("--strip-message", help="message under the photo strip (default: the title)")
    parser.add_argument("--strip-background", default=stripdesign.FALLBACK_BACKGROUND)
    parser.add_argument("--strip-text-color", default=stripdesign.TEXT_COLOR)
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--update-qr-ip", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_file = args.config_dir / "config.json"
    sync_file = args.config_dir / "plugin_synchronizer.json"

    ip = detect_lan_ip() if args.ip == "auto" else args.ip
    if not ip:
        print("Could not detect this PC's LAN IP (no network?). Pass it with --ip.", file=sys.stderr)
        return 1

    sync = load_json(sync_file)
    sync_common = sync.setdefault("common", {})

    if args.update_qr_ip:
        if not sync_common.get("enabled_custom_qr_url"):
            print("QR link not configured yet, nothing to update.")
            return 0
        if sync_common.get("custom_qr_url") == qr_url(ip):
            print(f"QR link already uses {ip}")
            return 0
        sync_common["custom_qr_url"] = qr_url(ip)
        SynchronizerCommon.model_validate(sync_common)
        write_json(sync_file, sync, args.dry_run)
        print(f"QR link updated to {ip}")
        return 0

    if not args.title:
        parser.error("--title is required (or use --update-qr-ip)")

    try:
        width, height = (int(x) for x in args.resolution.lower().split("x"))
    except ValueError:
        parser.error("--resolution must look like 1280x720")

    config = load_json(config_file)

    # --- common
    if args.admin_password:
        config.setdefault("common", {})["admin_password"] = args.admin_password
    GroupCommon.model_validate(config.get("common", {}))

    # --- webcam
    camera = choose_camera(args.camera)
    cameras = config.setdefault("cameras", {})
    cameras["index_backend_stills"] = 0
    cameras["index_backend_video"] = 0
    cameras["index_backend_multicam"] = 0
    cameras["group_backends"] = [
        {
            "enabled": True,
            "description": camera,
            "backend_config": {
                "backend_type": "WebcamPyav",
                "device_identifier": camera,
                "pixel_format": "auto",
                "cam_resolution_width": width,
                "cam_resolution_height": height,
                "cam_framerate": args.framerate,
            },
        }
    ]
    GroupCameras.model_validate(cameras)

    # --- QR only: no print/mail actions
    config.setdefault("share", {})["actions"] = []
    GroupShare.model_validate(config["share"])

    # --- first screen and idle behavior
    ui = config.setdefault("uisettings", {})
    ui.update(
        {
            "FRONTPAGE_TITLE": args.title,
            "FRONTPAGE_SHOW_DATE": True,
            "enable_livestream_when_idle": False,
            "enable_automatic_slideshow": False,
            "livestream_blurredbackground": False,
            # simple for the guests: no gallery button (the admin button stays visible, it asks for the password),
            # and the result screen offers only what is useful (sign, background, another one)
            "show_gallery_on_frontpage": False,
            "show_admin_on_frontpage": True,
            "admin_button_invisible": False,
            "gallery_show_download": False,
            "gallery_show_delete": False,
            "gallery_show_filter": False,
            "gallery_show_shareprint": False,
            "show_frontpage_timeout": 2,
        }
    )
    if args.strip_message:
        ui["STRIP_TEXT"] = args.strip_message
    GroupUiSettings.model_validate(ui)

    # --- photo strip collage
    if "actions" not in config:
        config["actions"] = GroupActions().model_dump(mode="json")
    if args.dry_run:
        background_image, frame_image = None, None
    else:
        background_image, frame_image = design_assets(ui.get("STRIP_TEXT") or args.title, args.strip_text_color)
    strip = build_action(STRIP_NAME, args.strip_background, background_image, frame_image)
    collages = config["actions"].setdefault("collage", [])
    existing = [i for i, a in enumerate(collages) if a.get("name") == STRIP_NAME]
    if existing:
        collages[existing[0]] = strip
    else:
        collages.append(strip)
    guest_buttons(config["actions"])
    GroupActions.model_validate(config["actions"])

    # --- QR link (the plugin must be enabled for QR codes to be generated)
    sync_common.update(
        {
            "enabled": True,
            "enabled_share_links": True,
            "enabled_custom_qr_url": True,
            "custom_qr_url": qr_url(ip),
        }
    )
    SynchronizerCommon.model_validate(sync_common)

    write_json(config_file, config, args.dry_run)
    write_json(sync_file, sync, args.dry_run)

    print(f"{'(dry run) ' if args.dry_run else ''}configured:")
    print(f"  title        : {args.title}")
    print(f"  webcam       : {camera} ({width}x{height} @ {args.framerate} fps)")
    print(f"  QR link      : {qr_url(ip)}")
    print(f"  strip message: {ui.get('STRIP_TEXT') or args.title}")
    print(f"  admin password {'set' if args.admin_password else 'unchanged'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
