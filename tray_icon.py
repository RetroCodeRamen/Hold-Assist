"""Windows system tray icon — load .ico from disk (avoids pystray PIL re-encode crashes)."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


def write_tray_ico_file(assets_dir: Path) -> Path:
    """
    Write a minimal 16×16 .ico under %TEMP% for LoadImage.

    pystray re-encoding large/custom JPG-derived icons often causes WinError 0 on W365.
    """
    temp_ico = Path(tempfile.gettempdir()) / "hold_assist_tray.ico"
    src = assets_dir / "tray.ico"
    if not src.exists():
        src = assets_dir / "icon.ico"
    if src.exists():
        try:
            with Image.open(src) as im:
                im.load()
                small = im.convert("RGBA").resize((16, 16), Image.Resampling.LANCZOS)
            small.save(temp_ico, format="ICO", sizes=[(16, 16)])
            return temp_ico
        except Exception as exc:
            logger.warning("Could not build tray ico from icon.ico: %s", exc)

    png = assets_dir / "icon.png"
    if png.exists():
        with Image.open(png) as im:
            small = im.convert("RGBA").resize((16, 16), Image.Resampling.LANCZOS)
        small.save(temp_ico, format="ICO", sizes=[(16, 16)])
        return temp_ico

    img = Image.new("RGBA", (16, 16), (30, 120, 200, 255))
    img.save(temp_ico, format="ICO", sizes=[(16, 16)])
    return temp_ico


def create_tray_icon(
    name: str,
    title: str,
    menu: Any,
    assets_dir: Path,
) -> Any:
    """Return a pystray Icon that loads the tray .ico file directly."""
    import pystray
    from pystray._win32 import Icon as Win32Icon

    ico_path = str(write_tray_ico_file(assets_dir).resolve())
    logger.info("Tray icon file: %s", ico_path)

    class FileTrayIcon(Win32Icon):
        def _assert_icon_handle(self) -> None:
            if self._icon_handle:
                return
            from pystray._util import win32

            handle = win32.LoadImage(
                None,
                ico_path,
                win32.IMAGE_ICON,
                0,
                0,
                win32.LR_LOADFROMFILE | win32.LR_DEFAULTSIZE,
            )
            if not handle:
                err = win32.GetLastError()
                raise OSError(err, f"LoadImage failed for tray icon: {ico_path}")
            self._icon_handle = handle

    placeholder = Image.new("RGB", (16, 16), (30, 120, 200))
    return FileTrayIcon(name, placeholder, title, menu)
