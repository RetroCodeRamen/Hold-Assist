"""
Hold Assist — monitor system audio for human speech during hold music.

Entry point: system tray, status window, and background VAD monitoring.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageDraw

from audio_capture import CHUNK_MS, AudioCapture
from audio_devices import DEFAULT_DEVICE_ID, OutputDevice, list_output_loopback_devices
from notifier import alert_background_effects, play_alert_sound
from settings import Settings, load_settings, save_settings
from crash_logging import setup_crash_logging
from icon_build import ensure_icons
from tray_icon import create_tray_icon
from vad_detector import VADLoadError, VADDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
LOG_FILE = setup_crash_logging()


def is_microsoft_store_python() -> bool:
    """
    Detect Microsoft Store Python even when running inside a venv.

    venv's sys.executable points at .venv\\Scripts\\python.exe, but pyvenv.cfg
    and sys.base_prefix still reference WindowsApps — that build crashes pystray/torch.
    """
    markers = ("windowsapps", "pythonsoftwarefoundation")

    def _has_marker(text: str) -> bool:
        t = text.lower()
        return any(m in t for m in markers)

    if _has_marker(sys.executable):
        return True
    if _has_marker(getattr(sys, "base_prefix", "")):
        return True

    for cfg_path in (
        Path(sys.prefix) / "pyvenv.cfg",
        Path(__file__).resolve().parent / ".venv" / "pyvenv.cfg",
    ):
        if cfg_path.is_file():
            try:
                if _has_marker(cfg_path.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                pass
    return False


def should_enable_tray(no_tray_flag: bool, force_tray: bool) -> bool:
    if no_tray_flag:
        return False
    if force_tray:
        return True
    # PyInstaller exe uses embedded runtime — tray is safe.
    if getattr(sys, "frozen", False):
        return True
    return not is_microsoft_store_python()

STATUS_IDLE = "Stopped"
STATUS_LISTENING = "Listening..."
STATUS_HOLD = "Hold music detected"
STATUS_PICKUP = "Someone picked up!"
STATUS_ERROR = "Error"
STATUS_COOLDOWN = "Alert sent — pausing..."

_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSETS_DIR = _BASE_DIR / "assets"
ICON_PNG = ASSETS_DIR / "icon.png"
ICON_ICO = ASSETS_DIR / "icon.ico"


class HoldAssistMonitor:
    """Background thread: audio chunks -> VAD -> sustained speech -> alert."""

    def __init__(
        self,
        settings: Settings,
        on_status: Callable[[str], None],
        on_error: Callable[[str], None],
        on_source: Optional[Callable[[str], None]] = None,
        on_fatal: Optional[Callable[[], None]] = None,
        on_alert: Optional[Callable[[], None]] = None,
    ) -> None:
        self.settings = settings
        self._on_status = on_status
        self._on_error = on_error
        self._on_source = on_source
        self._on_fatal = on_fatal
        self._on_alert = on_alert
        self._source_reported = False
        self._hold_streak_ms = 0.0
        self._was_in_hold_phase = False
        self._quiet_after_hold_ms = 0.0
        self._hold_energy_ema = 0.0
        self._music_gone_ms = 0.0
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._capture = AudioCapture(
            self._audio_queue,
            on_error=self._handle_capture_error,
            on_stopped=self._handle_capture_stopped,
            loopback_device_id=settings.output_device_id,
        )
        self._vad = VADDetector()
        self._stop = threading.Event()
        self._pause_until = 0.0
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._capture.set_loopback_device_id(settings.output_device_id)

    def start(self) -> None:
        if self._running:
            return
        try:
            self._vad.load()
        except VADLoadError as exc:
            self._on_error(str(exc))
            return

        self._stop.clear()
        self._pause_until = 0.0
        self._source_reported = False
        self._hold_streak_ms = 0.0
        self._was_in_hold_phase = False
        self._quiet_after_hold_ms = 0.0
        self._hold_energy_ema = 0.0
        self._music_gone_ms = 0.0
        self._capture.capture_source = ""
        self._capture.start()
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, name="Monitor", daemon=True)
        self._thread.start()
        self._on_status(STATUS_LISTENING)
        logger.info("Monitoring started")

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._capture.stop()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        self._on_status(STATUS_IDLE)
        logger.info("Monitoring stopped")

    def _handle_capture_error(self, message: str) -> None:
        """Called from the audio thread — do not join that thread here."""
        self._on_error(message)
        self._running = False
        self._stop.set()
        if self._on_fatal:
            self._on_fatal()

    def _handle_capture_stopped(self) -> None:
        if self._running and not self._stop.is_set():
            msg = (
                "Audio capture stopped unexpectedly. "
                f"See log: {LOG_FILE}"
            )
            if self._capture.last_error:
                msg = self._capture.last_error
            self._handle_capture_error(msg)

    def _trigger_pickup_alert(self, reason: str) -> None:
        if time.monotonic() < self._pause_until:
            return
        self._on_status(STATUS_PICKUP)
        logger.info("Pickup alert triggered (%s)", reason)
        if self._on_alert:
            self._on_alert()
        else:
            play_alert_sound()
        self._pause_until = time.monotonic() + self.settings.alert_cooldown_sec
        self._hold_streak_ms = 0.0
        self._was_in_hold_phase = False
        self._quiet_after_hold_ms = 0.0
        self._hold_energy_ema = 0.0
        self._music_gone_ms = 0.0

    def _update_hold_loudness(self, energy: float) -> None:
        if self._hold_energy_ema <= 0:
            self._hold_energy_ema = energy
        else:
            self._hold_energy_ema = 0.9 * self._hold_energy_ema + 0.1 * energy

    def _music_bed_present(self, energy: float) -> bool:
        """True while hold-music loudness is still present (ignores short voiceovers)."""
        floor = self.settings.audio_energy_threshold
        if self._hold_energy_ema > floor:
            return energy >= self._hold_energy_ema * self.settings.hold_music_drop_ratio
        return energy >= floor

    def _process_loop(self) -> None:
        speech_ms = 0.0
        chunk_ms = CHUNK_MS

        try:
            self._process_loop_inner(speech_ms, chunk_ms)
        except Exception as exc:
            logger.exception("Monitor thread crashed")
            self._on_error(f"Monitoring error: {exc}")
            self._running = False
            self._stop.set()

    def _process_loop_inner(self, speech_ms: float, chunk_ms: float) -> None:
        while not self._stop.is_set() and self._running:
            now = time.monotonic()
            if now < self._pause_until:
                self._on_status(STATUS_COOLDOWN)
                time.sleep(0.05)
                continue

            try:
                chunk = self._audio_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if (
                not self._source_reported
                and self._capture.capture_source
                and self._on_source
            ):
                self._source_reported = True
                self._on_source(self._capture.capture_source)

            energy = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
            try:
                confidence = self._vad.speech_confidence(chunk)
            except Exception as exc:
                logger.exception("VAD inference failed")
                self._on_error(f"VAD error: {exc}")
                break

            if self.settings.debug_mode:
                print(f"[VAD] conf={confidence:.3f} energy={energy:.4f}")

            threshold = self.settings.vad_threshold
            duration_ms = self.settings.speech_duration_sec * 1000.0
            min_hold_ms = self.settings.min_hold_before_alert_sec * 1000.0
            quiet_ms = self.settings.hold_end_quiet_sec * 1000.0
            post_hold_delay_ms = self.settings.post_hold_speech_delay_sec * 1000.0
            is_speech = confidence >= threshold
            music_bed = self._music_bed_present(energy)

            if music_bed:
                # Hold music still playing — includes periodic "your call is important" voice.
                self._update_hold_loudness(energy)
                self._hold_streak_ms += chunk_ms
                self._quiet_after_hold_ms = 0.0
                self._music_gone_ms = 0.0
                if self._hold_streak_ms >= min_hold_ms:
                    self._was_in_hold_phase = True
                speech_ms = 0.0
                self._on_status(STATUS_HOLD)
            elif self._was_in_hold_phase:
                # Hold phase ended — only alert once the music bed is actually gone.
                self._music_gone_ms += chunk_ms
                if energy < self.settings.audio_energy_threshold:
                    self._quiet_after_hold_ms += chunk_ms
                else:
                    self._quiet_after_hold_ms = 0.0

                self._on_status(STATUS_LISTENING)

                if self._quiet_after_hold_ms >= quiet_ms:
                    self._trigger_pickup_alert("hold_music_stopped")
                    speech_ms = 0.0
                elif is_speech and self._music_gone_ms >= post_hold_delay_ms:
                    speech_ms += chunk_ms
                    if speech_ms >= duration_ms:
                        self._trigger_pickup_alert("speech_after_music_ended")
                        speech_ms = 0.0
                else:
                    speech_ms = 0.0
            elif is_speech:
                speech_ms += chunk_ms
                if speech_ms >= duration_ms:
                    self._trigger_pickup_alert("sustained_speech")
                    speech_ms = 0.0
            else:
                speech_ms = 0.0
                if not self._was_in_hold_phase:
                    self._hold_streak_ms = 0.0
                    self._hold_energy_ema = 0.0
                self._on_status(STATUS_LISTENING)

        self._running = False


def _ensure_assets() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    ensure_icons(root, ASSETS_DIR)
    alert_wav = ASSETS_DIR / "alert.wav"
    if not alert_wav.exists():
        _write_beep_wav(alert_wav)


def _write_beep_wav(path: Path, rate: int = 22050, duration: float = 0.35) -> None:
    import math
    import struct
    import wave

    freq = 880.0
    n = int(rate * duration)
    samples = []
    for i in range(n):
        t = i / rate
        env = 1.0 if t < duration * 0.15 else max(0.0, 1.0 - (t - duration * 0.15) / (duration * 0.85))
        val = int(32767 * 0.4 * env * math.sin(2 * math.pi * freq * t))
        samples.append(struct.pack("<h", val))
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(samples))


class HoldAssistApp:
    """Tkinter UI + pystray + monitor controller."""

    def __init__(
        self,
        start_minimized: bool = False,
        auto_start_monitoring: bool = False,
        no_tray: bool = False,
        force_tray: bool = False,
    ) -> None:
        _ensure_assets()
        self.settings = load_settings()
        self._start_minimized = start_minimized
        self._launch_auto_start = auto_start_monitoring
        self._use_tray = should_enable_tray(no_tray, force_tray)
        self._store_python = is_microsoft_store_python()
        self._output_devices: list[OutputDevice] = []
        self._device_display_to_id: dict[str, str] = {}
        self._monitor: Optional[HoldAssistMonitor] = None
        self._tray_icon = None
        self._tray_thread: Optional[threading.Thread] = None
        self._pending_ui: queue.Queue[Callable[[], None]] = queue.Queue()

        self.root = tk.Tk()
        self._status_var = tk.StringVar(self.root, value=STATUS_IDLE)
        self._error_var = tk.StringVar(self.root, value="")
        self._source_var = tk.StringVar(
            self.root, value="Audio source: speaker loopback (not microphone)"
        )
        self.root.title("Hold Assist")
        self.root.geometry("480x440")
        self.root.minsize(440, 400)
        self._set_window_icon()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_window)

        self._monitor = HoldAssistMonitor(
            self.settings,
            on_status=self._schedule_status,
            on_error=self._schedule_error,
            on_source=self._schedule_source,
            on_fatal=lambda: self.root.after(0, self.stop_monitoring),
            on_alert=lambda: self.root.after(0, self._show_pickup_alert),
        )
        if self._use_tray:
            self.root.after(200, self._start_tray)
        else:
            reason = (
                "Microsoft Store Python detected — tray disabled (prevents crashes). "
                "Install Python from python.org and recreate .venv to enable tray."
                if self._store_python
                else "Tray disabled (--no-tray)."
            )
            logger.warning(reason)
            self._error_var.set(reason)

        self._poll_ui_queue()
        self._poll_capture_health()

        if self._start_minimized and self._use_tray:
            self.root.withdraw()
        if self._launch_auto_start or self.settings.auto_start_monitoring:
            self.root.after(3000, self._safe_auto_start_monitoring)

    def _safe_auto_start_monitoring(self) -> None:
        try:
            self.start_monitoring()
        except Exception as exc:
            logger.exception("Auto-start monitoring failed")
            self._schedule_error(f"Could not start monitoring: {exc}")

    def _set_window_icon(self) -> None:
        if ICON_ICO.exists():
            try:
                self.root.iconbitmap(str(ICON_ICO.resolve()))
                return
            except tk.TclError:
                pass
        if ICON_PNG.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(ICON_PNG))
                self.root.iconphoto(True, self._icon_image)
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Hold Assist", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", **pad
        )
        ttk.Label(frame, text="Status:").grid(row=1, column=0, sticky="w", **pad)
        status_lbl = ttk.Label(frame, textvariable=self._status_var, font=("Segoe UI", 11))
        status_lbl.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(frame, textvariable=self._error_var, foreground="red", wraplength=360).grid(
            row=2, column=0, columnspan=2, sticky="w", **pad
        )
        ttk.Label(
            frame,
            textvariable=self._source_var,
            font=("Segoe UI", 9),
            foreground="gray",
            wraplength=380,
        ).grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(frame, text="Listen on output:", font=("Segoe UI", 10, "bold")).grid(
            row=4, column=0, sticky="w", **pad
        )
        device_row = ttk.Frame(frame)
        device_row.grid(row=4, column=1, sticky="ew", **pad)
        device_row.columnconfigure(0, weight=1)
        self._device_combo = ttk.Combobox(device_row, state="readonly", width=36)
        self._device_combo.grid(row=0, column=0, sticky="ew")
        self._device_combo.bind("<<ComboboxSelected>>", self._on_output_device_changed)
        ttk.Button(device_row, text="Refresh", width=8, command=self._refresh_output_devices).grid(
            row=0, column=1, padx=(6, 0)
        )
        ttk.Label(
            frame,
            text="Choose the speakers or headphones used for your call (not a microphone).",
            font=("Segoe UI", 8),
            foreground="gray",
            wraplength=380,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=12)

        self._auto_start = tk.BooleanVar(self.root, value=self.settings.auto_start_monitoring)
        ttk.Checkbutton(
            frame,
            text="Start listening automatically when app opens",
            variable=self._auto_start,
            command=self._on_settings_changed,
        ).grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(frame, text="Settings", font=("Segoe UI", 11, "bold")).grid(
            row=8, column=0, columnspan=2, sticky="w", **pad
        )

        self._threshold = tk.DoubleVar(self.root, value=self.settings.vad_threshold)
        ttk.Label(frame, text="VAD sensitivity (threshold):").grid(row=9, column=0, sticky="w", **pad)
        thresh = ttk.Scale(
            frame,
            from_=0.2,
            to=0.9,
            variable=self._threshold,
            orient=tk.HORIZONTAL,
            command=self._on_settings_changed,
        )
        thresh.grid(row=9, column=1, sticky="ew", **pad)
        self._thresh_lbl = ttk.Label(frame, text=f"{self.settings.vad_threshold:.2f}")
        self._thresh_lbl.grid(row=10, column=1, sticky="w")

        self._duration = tk.DoubleVar(self.root, value=self.settings.speech_duration_sec)
        ttk.Label(frame, text="Speech duration before alert (sec):").grid(
            row=11, column=0, sticky="w", **pad
        )
        dur = ttk.Scale(
            frame,
            from_=1.0,
            to=6.0,
            variable=self._duration,
            orient=tk.HORIZONTAL,
            command=self._on_settings_changed,
        )
        dur.grid(row=11, column=1, sticky="ew", **pad)
        self._dur_lbl = ttk.Label(frame, text=f"{self.settings.speech_duration_sec:.1f}s")
        self._dur_lbl.grid(row=12, column=1, sticky="w")

        self._debug = tk.BooleanVar(self.root, value=self.settings.debug_mode)
        ttk.Checkbutton(
            frame,
            text="Debug mode (print VAD scores to console)",
            variable=self._debug,
            command=self._on_settings_changed,
        ).grid(row=13, column=0, columnspan=2, sticky="w", **pad)

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=14, column=0, columnspan=2, pady=12)
        ttk.Button(btn_row, text="Start", command=self.start_monitoring).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Stop", command=self.stop_monitoring).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Quit", command=self.quit_app).pack(side=tk.LEFT, padx=6)

        frame.columnconfigure(1, weight=1)
        ttk.Label(
            frame,
            text="Minimize to tray — right-click tray icon for Start/Stop/Quit.",
            font=("Segoe UI", 9),
            foreground="gray",
        ).grid(row=15, column=0, columnspan=2, sticky="w", **pad)

        self.root.after(50, self._refresh_output_devices)

    def _refresh_output_devices(self) -> None:
        try:
            self._output_devices = list_output_loopback_devices()
        except Exception as exc:
            logger.exception("Could not list output devices")
            self._error_var.set(f"Could not list audio outputs: {exc}")
            return

        labels: list[str] = []
        self._device_display_to_id = {}
        default_label = "Default — same as Windows playback device"
        labels.append(default_label)
        self._device_display_to_id[default_label] = DEFAULT_DEVICE_ID

        for dev in self._output_devices:
            label = dev.display_name
            if label in self._device_display_to_id:
                label = f"{label} [{dev.id[:8]}…]"
            labels.append(label)
            self._device_display_to_id[label] = dev.id

        self._device_combo["values"] = labels
        selected_label = default_label
        if self.settings.output_device_id:
            for lbl, dev_id in self._device_display_to_id.items():
                if dev_id == self.settings.output_device_id:
                    selected_label = lbl
                    break
        self._device_combo.set(selected_label)

    def _on_output_device_changed(self, _event=None) -> None:
        label = self._device_combo.get()
        device_id = self._device_display_to_id.get(label, DEFAULT_DEVICE_ID)
        self.settings.output_device_id = device_id
        save_settings(self.settings)
        if self._monitor:
            self._monitor.update_settings(self.settings)
        was_running = self._monitor and self._monitor.is_running
        if was_running:
            self.stop_monitoring()
            self.start_monitoring()

    def _schedule_source(self, source: str) -> None:
        self._pending_ui.put(lambda: self._source_var.set(source))

    def _show_pickup_alert(self) -> None:
        """Always show a visible popup on the main UI thread."""
        self._status_var.set(STATUS_PICKUP)
        self._deiconify()
        self.root.lift()
        try:
            self.root.attributes("-topmost", True)
            self.root.after(2500, lambda: self.root.attributes("-topmost", False))
        except tk.TclError:
            pass
        try:
            self.root.bell()
        except tk.TclError:
            pass
        messagebox.showinfo(
            "Hold Assist — Caller picked up?",
            "Hold music stopped or someone is speaking.\n\nCheck your call now.",
            parent=self.root,
        )
        threading.Thread(target=alert_background_effects, name="Notifier", daemon=True).start()

    def _on_settings_changed(self, *_args) -> None:
        self.settings.vad_threshold = float(self._threshold.get())
        self.settings.speech_duration_sec = float(self._duration.get())
        self.settings.debug_mode = bool(self._debug.get())
        self.settings.auto_start_monitoring = bool(self._auto_start.get())
        self.settings.clamp()
        self._thresh_lbl.config(text=f"{self.settings.vad_threshold:.2f}")
        self._dur_lbl.config(text=f"{self.settings.speech_duration_sec:.1f}s")
        save_settings(self.settings)
        if self._monitor:
            self._monitor.update_settings(self.settings)

    def _schedule_status(self, status: str) -> None:
        self._pending_ui.put(lambda: self._status_var.set(status))

    def _schedule_error(self, message: str) -> None:
        def _apply() -> None:
            self._error_var.set(message)
            self._status_var.set(STATUS_ERROR)
            messagebox.showerror("Hold Assist", message)

        self._pending_ui.put(_apply)

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                fn = self._pending_ui.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui_queue)

    def _poll_capture_health(self) -> None:
        if self._monitor and self._monitor.is_running and not self._monitor._capture.is_running:
            self._monitor._handle_capture_stopped()
        self.root.after(500, self._poll_capture_health)

    def start_monitoring(self) -> None:
        self._error_var.set("")
        if self._monitor:
            self._on_settings_changed()
            self._monitor.start()

    def stop_monitoring(self) -> None:
        if self._monitor:
            self._monitor.stop()

    def _on_close_window(self) -> None:
        self.root.withdraw()

    def quit_app(self) -> None:
        self.stop_monitoring()
        if self._tray_icon:
            self._tray_icon.stop()
        self.root.quit()
        self.root.destroy()

    def _start_tray(self) -> None:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Show window", self._show_window, default=True),
                pystray.MenuItem("Start", self._tray_start),
                pystray.MenuItem("Stop", self._tray_stop),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._tray_quit),
            )
            self._tray_icon = create_tray_icon(
                "hold_assist", "Hold Assist", menu, ASSETS_DIR
            )

            def _run() -> None:
                try:
                    self._tray_icon.run()
                except Exception as exc:
                    logger.error("System tray stopped: %s", exc)

            self._tray_thread = threading.Thread(target=_run, name="TrayIcon", daemon=True)
            self._tray_thread.start()
            logger.info("System tray started")
        except Exception as exc:
            logger.error("System tray unavailable (app still works): %s", exc)
            self._tray_icon = None
            self._error_var.set(
                "Tray icon failed to load — use the Hold Assist window. "
                f"({exc})"
            )

    def _show_window(self, _icon=None, _item=None) -> None:
        self.root.after(0, self._deiconify)

    def _deiconify(self) -> None:
        self.root.deiconify()
        self.root.lift()

    def _tray_start(self, _icon=None, _item=None) -> None:
        self.root.after(0, self.start_monitoring)

    def _tray_stop(self, _icon=None, _item=None) -> None:
        self.root.after(0, self.stop_monitoring)

    def _tray_quit(self, _icon=None, _item=None) -> None:
        self.root.after(0, self.quit_app)

    def run(self) -> None:
        try:
            self.root.mainloop()
        except Exception:
            logger.exception("Main loop error")
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Hold Assist — alert when hold music ends")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized to the system tray",
    )
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Start listening automatically (used by Windows sign-in shortcut)",
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Disable system tray (recommended on Microsoft Store Python)",
    )
    parser.add_argument(
        "--force-tray",
        action="store_true",
        help="Enable tray even on Store Python (may crash)",
    )
    args = parser.parse_args()
    try:
        app = HoldAssistApp(
            start_minimized=args.minimized,
            auto_start_monitoring=args.autostart,
            no_tray=args.no_tray,
            force_tray=args.force_tray,
        )
        app.run()
        return 0
    except Exception as exc:
        logger.exception("Fatal error")
        messagebox.showerror("Hold Assist", f"Failed to start: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
