"""Persist and load Hold Assist user configuration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

APP_NAME = "HoldAssist"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "settings.json"


@dataclass
class Settings:
    """User-tunable monitoring parameters."""

    vad_threshold: float = 0.5
    speech_duration_sec: float = 2.5
    alert_cooldown_sec: float = 10.0
    debug_mode: bool = False
    audio_energy_threshold: float = 0.01
    # Alert when hold music was playing, then output goes quiet (status -> Listening).
    min_hold_before_alert_sec: float = 3.0
    hold_end_quiet_sec: float = 0.6
    # Energy must fall below this fraction of peak hold loudness to count as "music stopped".
    hold_music_drop_ratio: float = 0.5
    # Seconds of low energy (music gone) before speech can trigger pickup.
    post_hold_speech_delay_sec: float = 1.0
    # WASAPI id of speaker/headphone output to monitor; "" = Windows default playback.
    output_device_id: str = ""
    # Start monitoring when the app opens (useful with sign-in startup).
    auto_start_monitoring: bool = False

    def clamp(self) -> "Settings":
        self.vad_threshold = max(0.1, min(0.95, self.vad_threshold))
        self.speech_duration_sec = max(1.0, min(10.0, self.speech_duration_sec))
        self.alert_cooldown_sec = max(5.0, min(60.0, self.alert_cooldown_sec))
        self.audio_energy_threshold = max(0.001, min(0.1, self.audio_energy_threshold))
        self.min_hold_before_alert_sec = max(1.0, min(120.0, self.min_hold_before_alert_sec))
        self.hold_end_quiet_sec = max(0.2, min(5.0, self.hold_end_quiet_sec))
        self.hold_music_drop_ratio = max(0.25, min(0.85, self.hold_music_drop_ratio))
        self.post_hold_speech_delay_sec = max(0.0, min(5.0, self.post_hold_speech_delay_sec))
        return self


def _defaults() -> dict[str, Any]:
    return asdict(Settings())


def load_settings() -> Settings:
    """Load settings from disk, or return defaults if missing/invalid."""
    if not CONFIG_PATH.exists():
        return Settings()

    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
        base = _defaults()
        base.update({k: v for k, v in raw.items() if k in base})
        settings = Settings(**base)
        return settings.clamp()
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return Settings()


def save_settings(settings: Settings) -> None:
    """Write settings to the user config directory."""
    settings.clamp()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2)
