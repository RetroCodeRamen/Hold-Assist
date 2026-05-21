"""List WASAPI loopback (speaker output) devices for user selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import soundcard as sc

logger = logging.getLogger(__name__)

# Stored in settings.json — follow Windows default playback device.
DEFAULT_DEVICE_ID = ""


@dataclass(frozen=True)
class OutputDevice:
    """A speaker/output device that can be monitored via loopback."""

    id: str
    name: str
    is_windows_default: bool = False

    @property
    def display_name(self) -> str:
        suffix = " (Windows default)" if self.is_windows_default else ""
        return f"{self.name}{suffix}"


def _safe_name(device: sc.Microphone | sc.Speaker) -> str:
    try:
        return str(device.name)
    except Exception as exc:
        logger.debug("Could not read device name: %s", exc)
        return str(getattr(device, "id", "Unknown device"))


def list_output_loopback_devices() -> List[OutputDevice]:
    """
    Return playback outputs available for loopback capture.

    Each entry is the audio heard on that speaker/headphone endpoint
    (not a physical microphone).
    """
    try:
        default_speaker = sc.default_speaker()
        default_id = default_speaker.id if default_speaker else None
    except Exception:
        default_id = None

    loopbacks = [
        m
        for m in sc.all_microphones(include_loopback=True)
        if getattr(m, "isloopback", False)
    ]

    devices: List[OutputDevice] = []
    seen_ids: set[str] = set()
    for mic in loopbacks:
        dev_id = str(mic.id)
        if dev_id in seen_ids:
            continue
        seen_ids.add(dev_id)
        devices.append(
            OutputDevice(
                id=dev_id,
                name=_safe_name(mic),
                is_windows_default=default_id is not None and dev_id == default_id,
            )
        )

    devices.sort(key=lambda d: (not d.is_windows_default, d.name.lower()))
    return devices


def resolve_loopback_device(device_id: Optional[str] = None) -> sc.Microphone:
    """
    Find loopback Microphone for the given output device id.

    Empty device_id uses the current Windows default playback device.
    """
    loopbacks = [
        m
        for m in sc.all_microphones(include_loopback=True)
        if getattr(m, "isloopback", False)
    ]
    if not loopbacks:
        raise RuntimeError(
            "No loopback devices found. Enable speakers or headphones in Windows Sound settings."
        )

    use_default = not device_id or device_id == DEFAULT_DEVICE_ID
    if not use_default:
        for mic in loopbacks:
            if mic.id == device_id:
                if not getattr(mic, "isloopback", False):
                    raise RuntimeError("Selected device is not a loopback endpoint.")
                return mic
        raise RuntimeError(
            f"Selected output device is not available: {device_id}. "
            "Click Refresh and choose another device."
        )

    speaker = sc.default_speaker()
    if speaker is None:
        raise RuntimeError("No default Windows playback device found.")

    for mic in loopbacks:
        if mic.id == speaker.id:
            return mic

    for mic in loopbacks:
        try:
            if mic.name == speaker.name:
                return mic
        except RuntimeError:
            continue

    raise RuntimeError(
        f"No loopback for default output '{_safe_name(speaker)}'. "
        "Select the speaker or headphones you use for calls in the list above."
    )
