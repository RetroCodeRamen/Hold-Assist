"""Generate icon.png, icon.ico (from icon.jpg if present), and alert.wav."""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from icon_build import ensure_icons  # noqa: E402

ASSETS = ROOT / "assets"


def make_alert_wav(path: Path, rate: int = 22050, duration: float = 0.35) -> None:
    freq = 880.0
    n = int(rate * duration)
    frames = []
    for i in range(n):
        t = i / rate
        env = 1.0 if t < duration * 0.15 else max(0.0, 1.0 - (t - duration * 0.15) / (duration * 0.85))
        val = int(32767 * 0.4 * env * math.sin(2 * math.pi * freq * t))
        frames.append(struct.pack("<h", val))
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    from_user = ensure_icons(ROOT, ASSETS, force=True)
    make_alert_wav(ASSETS / "alert.wav")
    if from_user:
        print(f"Icons built from your image -> {ASSETS}")
    else:
        print(f"No icon.jpg found; placeholder icons -> {ASSETS}")
        print("  Place icon.jpg in the project folder or assets/ folder and re-run.")
    print(f"Assets written to {ASSETS}")


if __name__ == "__main__":
    main()
