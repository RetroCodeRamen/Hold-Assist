"""Install handlers so crashes in threads and native code are logged."""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


def default_log_path() -> Path:
    """Installed app logs to AppData; dev mode logs next to project."""
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("APPDATA", Path.home())) / "HoldAssist"
        base.mkdir(parents=True, exist_ok=True)
        return base / "hold_assist.log"
    return Path(__file__).resolve().parent / "hold_assist.log"


def setup_crash_logging(log_path: Path | None = None) -> Path:
    """Enable file logging, thread exception hook, and faulthandler."""
    path = log_path or default_log_path()
    root = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(fh)

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        thread_name = getattr(args.thread, "name", "")
        # pystray tray thread can fail on W365/RDP; do not treat as fatal.
        if thread_name == "TrayIcon":
            logger.error(
                "Tray icon thread error (non-fatal)",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            return
        logger.critical(
            "Uncaught exception in thread %s",
            thread_name or args.thread,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        traceback.print_exception(
            args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr
        )

    threading.excepthook = _thread_hook

    def _sys_hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _sys_hook

    try:
        import faulthandler

        with open(path, "a", encoding="utf-8") as fh:
            faulthandler.enable(file=fh)
    except Exception as exc:
        logger.debug("faulthandler not enabled: %s", exc)

    logger.info("Crash logging enabled; log file: %s", path)
    return path
