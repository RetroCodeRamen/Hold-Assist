"""Build icon.png / icon.ico from icon.jpg (or other source image)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

SOURCE_NAMES = ("icon.jpg", "icon.jpeg", "Icon.jpg", "Icon.jpeg")


def find_icon_source(root: Path, assets: Path) -> Optional[Path]:
    """Locate user-provided icon.jpg in assets/ or project root."""
    for directory in (assets, root):
        for name in SOURCE_NAMES:
            path = directory / name
            if path.is_file():
                return path
    return None


def _square_crop(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def build_icons_from_image(source: Path, assets_dir: Path) -> None:
    """Create icon.png and icon.ico for window, tray, and installer."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        img = im.convert("RGBA")
    img = _square_crop(img)
    master = img.resize((256, 256), Image.Resampling.LANCZOS)
    png_path = assets_dir / "icon.png"
    ico_path = assets_dir / "icon.ico"
    master.save(png_path, format="PNG")
    master.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    # Dedicated small tray file (pystray is picky on W365).
    tray = img.resize((16, 16), Image.Resampling.LANCZOS)
    tray.save(assets_dir / "tray.ico", format="ICO", sizes=[(16, 16)])
    logger.info("Icons built from %s -> %s, %s", source, png_path, ico_path)


def build_placeholder_icons(assets_dir: Path) -> None:
    """Fallback icon when no icon.jpg is present."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (256, 256), (30, 120, 200, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse((32, 32, 224, 224), fill=(255, 255, 255, 230))
    draw.rectangle((112, 80, 144, 176), fill=(30, 120, 200, 255))
    draw.pieslice((72, 112, 184, 208), 0, 180, fill=(30, 120, 200, 255))
    img.save(assets_dir / "icon.png", format="PNG")
    img.save(
        assets_dir / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    img.resize((16, 16), Image.Resampling.LANCZOS).save(
        assets_dir / "tray.ico", format="ICO", sizes=[(16, 16)]
    )


def ensure_icons(root: Path, assets_dir: Path, force: bool = False) -> bool:
    """
    Build icons if icon.jpg exists or outputs are missing.

    Returns True if icons were built from a user image.
    """
    source = find_icon_source(root, assets_dir)
    png_path = assets_dir / "icon.png"
    ico_path = assets_dir / "icon.ico"

    if source is not None:
        stale = (
            force
            or not png_path.exists()
            or not ico_path.exists()
            or source.stat().st_mtime > png_path.stat().st_mtime
            or source.stat().st_mtime > ico_path.stat().st_mtime
        )
        if stale:
            build_icons_from_image(source, assets_dir)
        return True

    if not png_path.exists() or not ico_path.exists():
        build_placeholder_icons(assets_dir)
    return False
