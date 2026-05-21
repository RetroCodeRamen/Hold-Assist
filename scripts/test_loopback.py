"""Record 5 seconds of speaker loopback to verify WASAPI capture works."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import soundcard as sc

from audio_capture import AudioCapture


def main() -> int:
    q = __import__("queue").Queue()
    cap = AudioCapture(q, loopback_device_id="")
    cap.start()
    print("Recording loopback for 5s...", cap.capture_source or "(starting)")
    deadline = time.time() + 5.0
    chunks = 0
    while time.time() < deadline:
        if not cap.is_running:
            print("Capture thread died:", cap.last_error)
            return 1
        try:
            q.get(timeout=0.5)
            chunks += 1
        except Exception:
            pass
    cap.stop()
    print(f"OK: received {chunks} chunks")
    return 0 if chunks > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
