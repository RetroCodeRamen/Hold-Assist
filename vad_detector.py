"""Silero VAD model loading and per-chunk speech confidence scoring."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from audio_capture import CHUNK_SAMPLES, SAMPLE_RATE

logger = logging.getLogger(__name__)

_BUNDLE_REPO = Path(__file__).resolve().parent / "bundle" / "silero_vad"


class VADLoadError(Exception):
    """Raised when the Silero VAD model cannot be loaded."""


class VADDetector:
    """Wrap Silero VAD for streaming confidence on 16 kHz mono chunks."""

    def __init__(self) -> None:
        self._model = None
        self._device = torch.device("cpu")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @staticmethod
    def _bundled_repo_path() -> Optional[Path]:
        """Path to Silero VAD included in PyInstaller build (offline on user PCs)."""
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", ""))
            candidate = base / "silero_vad"
            if candidate.is_dir():
                return candidate
        if _BUNDLE_REPO.is_dir():
            return _BUNDLE_REPO
        return None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            bundled = self._bundled_repo_path()
            if bundled is not None:
                logger.info("Loading Silero VAD from bundled copy: %s", bundled)
                model, _utils = torch.hub.load(
                    repo_or_dir=str(bundled),
                    model="silero_vad",
                    source="local",
                    force_reload=False,
                    trust_repo=True,
                )
            else:
                logger.info("Loading Silero VAD from torch.hub (dev / first-time download)...")
                model, _utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    trust_repo=True,
                )
            self._model = model.to(self._device)
            self._model.eval()
            logger.info("Silero VAD model loaded")
        except Exception as exc:
            raise VADLoadError(
                f"Failed to load Silero VAD: {exc}. "
                "On the build PC, run scripts/build_installer.ps1 to bundle the model."
            ) from exc

    def unload(self) -> None:
        self._model = None

    @torch.inference_mode()
    def speech_confidence(self, chunk: np.ndarray) -> float:
        """
        Return speech probability in [0, 1] for one 30 ms chunk.

        Expects float32 mono numpy array of length CHUNK_SAMPLES.
        """
        if self._model is None:
            raise RuntimeError("VAD model not loaded. Call load() first.")

        audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if audio.size < CHUNK_SAMPLES:
            audio = np.pad(audio, (0, CHUNK_SAMPLES - audio.size))
        elif audio.size > CHUNK_SAMPLES:
            audio = audio[:CHUNK_SAMPLES]

        # Silero expects roughly [-1, 1]; loopback can clip — normalize lightly
        peak = np.max(np.abs(audio))
        if peak > 1e-6:
            audio = audio / max(peak, 1.0)

        tensor = torch.from_numpy(audio).to(self._device)
        prob = self._model(tensor, SAMPLE_RATE).item()
        return float(prob)
