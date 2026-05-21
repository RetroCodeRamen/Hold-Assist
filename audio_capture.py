"""WASAPI loopback capture via soundcard, resampled to 16 kHz mono chunks."""

from __future__ import annotations

import logging
import queue
import sys
import threading
import traceback
from typing import Callable, Optional

import numpy as np
import soundcard as sc

from audio_devices import resolve_loopback_device

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
# Silero VAD uses a 512-sample window at 16 kHz (~32 ms).
CHUNK_SAMPLES = 512
CHUNK_MS = CHUNK_SAMPLES / SAMPLE_RATE * 1000.0
# WASAPI is more stable with blocksize > numframes (soundcard docs).
WASAPI_BLOCKSIZE = max(CHUNK_SAMPLES * 8, 4096)


class AudioCaptureError(Exception):
    """Raised when loopback capture cannot be started."""


class AudioCapture:
    """Capture system output in a background thread and enqueue ~32 ms chunks."""

    def __init__(
        self,
        out_queue: queue.Queue[np.ndarray],
        on_error: Optional[Callable[[str], None]] = None,
        on_stopped: Optional[Callable[[], None]] = None,
        loopback_device_id: str = "",
    ) -> None:
        self._queue = out_queue
        self._on_error = on_error
        self._on_stopped = on_stopped
        self._loopback_device_id = loopback_device_id
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.capture_source: str = ""
        self.last_error: str = ""

    def set_loopback_device_id(self, device_id: str) -> None:
        self._loopback_device_id = device_id or ""

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self.last_error = ""
        self._thread = threading.Thread(target=self._run_safe, name="AudioCapture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _emit_error(self, message: str) -> None:
        self.last_error = message
        logger.error(message)
        if self._on_error:
            self._on_error(message)

    def _run_safe(self) -> None:
        try:
            self._run()
        except Exception as exc:
            msg = f"Audio capture thread crashed: {exc}"
            logger.critical(msg)
            logger.critical(traceback.format_exc())
            self._emit_error(msg)
        finally:
            if self._on_stopped and not self._stop.is_set():
                try:
                    self._on_stopped()
                except Exception:
                    logger.exception("on_stopped callback failed")

    def _find_loopback_mic(self) -> sc.Microphone:
        try:
            mic = resolve_loopback_device(self._loopback_device_id)
            logger.info(
                "Loopback device id=%s (selected=%s)",
                mic.id,
                self._loopback_device_id or "Windows default",
            )
            return mic
        except RuntimeError as exc:
            raise AudioCaptureError(str(exc)) from exc

    @staticmethod
    def _record_channels(loopback: sc.Microphone) -> int:
        """
        Channel count for WASAPI loopback.

        soundcard documents that single-channel loopback on Windows can fail;
        always use at least 2 channels there.
        """
        try:
            n = int(loopback.channels)
        except Exception:
            n = 2
        if sys.platform == "win32":
            return max(2, n)
        return max(1, n)

    @staticmethod
    def _to_mono(block: np.ndarray) -> np.ndarray:
        data = np.asarray(block, dtype=np.float32)
        if data.size == 0:
            return np.zeros(0, dtype=np.float32)
        if data.ndim == 1:
            return data.reshape(-1)
        if data.ndim == 2:
            # soundcard: (frames, channels)
            if data.shape[0] < data.shape[1] and data.shape[0] <= 8:
                data = data.T
            return data.mean(axis=1).astype(np.float32)
        return data.reshape(-1).astype(np.float32)

    @staticmethod
    def _resample_to_16k(data: np.ndarray, source_rate: int) -> np.ndarray:
        if source_rate == SAMPLE_RATE:
            return data.astype(np.float32, copy=False)
        target_len = int(len(data) * SAMPLE_RATE / source_rate)
        if target_len < 1:
            return np.zeros(0, dtype=np.float32)
        x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
        return np.interp(x_new, x_old, data).astype(np.float32)

    def _push_buffer(
        self, buffer: np.ndarray, mono: np.ndarray
    ) -> np.ndarray:
        buffer = np.concatenate((buffer, mono))
        while len(buffer) >= CHUNK_SAMPLES and not self._stop.is_set():
            chunk = buffer[:CHUNK_SAMPLES].copy()
            buffer = buffer[CHUNK_SAMPLES:]
            try:
                self._queue.put(chunk, timeout=0.5)
            except queue.Full:
                pass
        return buffer

    def _capture_stream(
        self,
        loopback: sc.Microphone,
        samplerate: int,
        channels: int,
    ) -> None:
        frames_per_read = int(samplerate * CHUNK_MS / 1000)
        buffer = np.zeros(0, dtype=np.float32)

        with loopback.recorder(
            samplerate=samplerate,
            channels=channels,
            blocksize=WASAPI_BLOCKSIZE,
        ) as recorder:
            logger.info(
                "Loopback recording: rate=%s channels=%s blocksize=%s",
                samplerate,
                channels,
                WASAPI_BLOCKSIZE,
            )
            while not self._stop.is_set():
                block = recorder.record(numframes=frames_per_read)
                mono = self._to_mono(block)
                if samplerate != SAMPLE_RATE:
                    mono = self._resample_to_16k(mono, samplerate)
                buffer = self._push_buffer(buffer, mono)

    def _run(self) -> None:
        loopback = self._find_loopback_mic()

        if not getattr(loopback, "isloopback", False):
            self._emit_error(
                "Internal error: selected device is not loopback. "
                "Refusing to record from a physical microphone."
            )
            return

        try:
            device_name = loopback.name
        except RuntimeError:
            device_name = str(loopback.id)
        self.capture_source = f"Listening on: {device_name}"

        channels = self._record_channels(loopback)
        configs = [
            (SAMPLE_RATE, channels),
            (48_000, channels),
            (SAMPLE_RATE, max(2, channels)),
        ]
        # Deduplicate configs
        seen: set[tuple[int, int]] = set()
        unique_configs = []
        for cfg in configs:
            if cfg not in seen:
                seen.add(cfg)
                unique_configs.append(cfg)

        last_exc: Optional[Exception] = None
        for samplerate, ch in unique_configs:
            try:
                logger.info(
                    "Loopback capture started — %s (trying %s Hz, %s ch)",
                    self.capture_source,
                    samplerate,
                    ch,
                )
                self._capture_stream(loopback, samplerate, ch)
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Loopback failed at %s Hz / %s ch: %s",
                    samplerate,
                    ch,
                    exc,
                )

        self._emit_error(
            f"Loopback capture failed after all attempts: {last_exc}. "
            "If using Remote Desktop, try local speakers/headphones as default output."
        )
        logger.info("Loopback capture stopped")
