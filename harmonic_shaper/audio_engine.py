"""Real-time additive synthesis engine using sounddevice."""

import logging
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    sd = None  # type: ignore

from .state import VoiceParameterStore

log = logging.getLogger(__name__)


class AudioEngine:
    """Stereo additive synthesis engine.

    Generates pure sine tones for each active harmonic with independent
    gain, stereo pan (equal-power law), and phase offset.

    Thread-safety model:
        • The audio callback runs in a C-level PortAudio thread.
        • It calls store.get_snapshot() which holds the store lock briefly
          (~microseconds for a small dict copy) then releases it.
        • All other threads (MIDI, HTTP, OSC) write to the store under the
          same lock — they may be delayed up to one callback period (~5 ms
          at 256-sample blocks / 44100 Hz) when the callback is running.
        • This is acceptable for a cymatic control application.
    """

    def __init__(
        self,
        store: VoiceParameterStore,
        sample_rate: int = 44100,
        block_size: int = 256,
        device: Optional[int | str] = None,
    ):
        if not HAS_SOUNDDEVICE:
            raise ImportError(
                "sounddevice is required. Install with: pip install sounddevice"
            )
        self._store = store
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._device = device
        self._stream: Optional["sd.OutputStream"] = None
        # Phase accumulators per harmonic_n — only touched by the callback thread
        self._phase_acc: dict[int, float] = {}
        self._running = False

    # ─── Public API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            blocksize=self._block_size,
            channels=2,
            dtype="float32",
            device=self._device,
            callback=self._audio_callback,
            finished_callback=self._on_stream_finished,
        )
        self._stream.start()
        self._running = True
        log.info(
            "Audio engine started — sr=%d  block=%d  device=%s",
            self._sample_rate, self._block_size, self._device,
        )

    def stop(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                log.warning("Error closing stream: %s", exc)
            self._stream = None
        log.info("Audio engine stopped")

    @property
    def is_running(self) -> bool:
        return bool(self._running and self._stream and self._stream.active)

    @staticmethod
    def list_devices() -> str:
        """Human-readable device list."""
        if HAS_SOUNDDEVICE:
            return str(sd.query_devices())
        return "(sounddevice not installed)"

    # ─── Audio callback ───────────────────────────────────────────────────────

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info,
        status: "sd.CallbackFlags",
    ) -> None:
        """Called by PortAudio — fills `outdata` with stereo float32 samples."""
        if status:
            log.debug("Audio status: %s", status)

        voices = self._store.get_snapshot()  # brief lock, then released
        mix = np.zeros((frames, 2), dtype=np.float32)

        for n, params in voices.items():
            if params.freq <= 0:
                continue

            # Sample-precise time indices
            t = np.arange(frames, dtype=np.float64) / self._sample_rate

            # Phase continuity across callbacks
            start_phase = self._phase_acc.get(n, 0.0)
            carrier_phases = 2.0 * np.pi * params.freq * t + start_phase

            # Sine with shaping phase offset (controls relative phase between harmonics)
            sine = np.sin(carrier_phases + params.phase).astype(np.float32)
            sine *= float(params.gain)

            # Advance accumulator — modulo to prevent float precision drift
            self._phase_acc[n] = (
                carrier_phases[-1] + 2.0 * np.pi * params.freq / self._sample_rate
            ) % (2.0 * np.pi)

            # Equal-power stereo pan: pan=-1 → full left, pan=+1 → full right
            angle = (float(params.pan) + 1.0) * (np.pi / 4.0)
            mix[:, 0] += sine * float(np.cos(angle))
            mix[:, 1] += sine * float(np.sin(angle))

        # Prune accumulators for voices that went inactive
        for n in [k for k in list(self._phase_acc) if k not in voices]:
            del self._phase_acc[n]

        mix *= self._store.get_master_gain()
        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix

    def _on_stream_finished(self) -> None:
        log.warning("Audio stream finished unexpectedly — hardware disconnect?")
        self._running = False
