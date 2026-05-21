"""Windows notifications and alert sound playback."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

APP_TITLE = "Hold Assist"
ALERT_MESSAGE = "Hold music stopped — someone may have picked up! Check your call."

_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSETS_DIR = _BASE_DIR / "assets"
ALERT_WAV = ASSETS_DIR / "alert.wav"


def play_alert_sound() -> None:
    if not ALERT_WAV.exists():
        logger.warning("Alert sound not found at %s", ALERT_WAV)
        return
    try:
        import winsound

        winsound.PlaySound(str(ALERT_WAV), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as exc:
        logger.warning("Could not play alert sound: %s", exc)


def show_windows_message_box(title: str, message: str) -> None:
    """Blocking popup that works on all Windows versions (main thread only)."""
    if sys.platform != "win32":
        logger.info("%s: %s", title, message)
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            message,
            title,
            0x00000040 | 0x00040000,  # MB_ICONINFORMATION | MB_TOPMOST
        )
        logger.info("MessageBox shown")
    except Exception as exc:
        logger.warning("MessageBox failed: %s", exc)


def show_toast(title: str, message: str) -> None:
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name=APP_TITLE,
            timeout=10,
        )
        logger.info("Toast sent via plyer")
        return
    except Exception as exc:
        logger.debug("plyer notification failed: %s", exc)

    try:
        from win10toast import ToastNotifier

        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=8, threaded=True)
        logger.info("Toast sent via win10toast")
    except Exception as exc2:
        logger.warning("Toast notification failed: %s", exc2)


def alert_background_effects() -> None:
    """Sound + toast from a worker thread (no UI)."""
    play_alert_sound()
    show_toast(APP_TITLE, ALERT_MESSAGE)


def alert_human_detected(async_notify: bool = True) -> None:
    """Play sound and try a toast (legacy entry point)."""
    if async_notify:
        threading.Thread(target=alert_background_effects, name="Notifier", daemon=True).start()
    else:
        alert_background_effects()
