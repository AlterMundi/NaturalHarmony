"""Thread-safe voice parameter store."""

import math
import threading
from copy import copy
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class VoiceParams:
    """Parameters for a single harmonic voice."""
    harmonic_n: int = 0
    freq: float = 0.0      # Hz — set by beacon broadcast
    gain: float = 0.8      # 0.0 to 1.0
    pan: float = 0.0       # -1.0 (left) to +1.0 (right)
    phase: float = 0.0     # radians — 0 to 2π
    active: bool = False
    voice_id: Optional[int] = None

    def copy(self) -> "VoiceParams":
        return copy(self)

    def to_dict(self) -> dict:
        return {
            "harmonic_n": self.harmonic_n,
            "freq": round(self.freq, 3),
            "gain": round(self.gain, 4),
            "pan": round(self.pan, 4),
            "phase_deg": round(math.degrees(self.phase) % 360, 1),
            "active": self.active,
        }


class VoiceParameterStore:
    """Thread-safe store for per-harmonic shaper parameters.

    Keyed by harmonic_n (e.g. 1 = fundamental, 2 = octave …).
    The beacon populates voice_on/off/freq; control surfaces set gain/pan/phase.
    """

    def __init__(self, on_change: Optional[Callable[[], None]] = None):
        self._lock = threading.RLock()
        self._voices: dict[int, VoiceParams] = {}
        # Chronological list of active harmonic_n values to enforce 5-voice polyphony (note stealing)
        self._active_history: list[int] = []
        self.f1: float = 65.0       # Base frequency
        self._on_change = on_change

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _notify(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def _ensure(self, n: int) -> None:
        """Create slot if absent. Caller must hold lock."""
        if n not in self._voices:
            self._voices[n] = VoiceParams(harmonic_n=n)

    # ─── Beacon-driven lifecycle ───────────────────────────────────────────────

    def voice_on(self, harmonic_n: int, voice_id: int, freq: float, gain: float = 0.8) -> None:
        with self._lock:
            self._ensure(harmonic_n)
            v = self._voices[harmonic_n]
            v.voice_id = voice_id
            v.freq = freq
            v.active = True

            # Implement 5-voice note stealing
            if harmonic_n in self._active_history:
                self._active_history.remove(harmonic_n)
            self._active_history.append(harmonic_n)
            
            while len(self._active_history) > 5:
                oldest_n = self._active_history.pop(0)
                self._voices[oldest_n].active = False

        self._notify()

    def voice_off(self, voice_id: int) -> None:
        with self._lock:
            for n, v in self._voices.items():
                if v.voice_id == voice_id:
                    v.active = False
                    if n in self._active_history:
                        self._active_history.remove(n)
        self._notify()

    def voice_freq(self, voice_id: int, freq: float) -> None:
        """Update frequency for LFO sweep continuity."""
        with self._lock:
            for v in self._voices.values():
                if v.voice_id == voice_id:
                    v.freq = freq

    def update_f1(self, f1: float) -> None:
        self.f1 = f1

    # ─── Parameter control ────────────────────────────────────────────────────

    def set_gain(self, harmonic_n: int, gain: float) -> None:
        with self._lock:
            self._ensure(harmonic_n)
            self._voices[harmonic_n].gain = max(0.0, min(1.0, gain))
        self._notify()

    def set_pan(self, harmonic_n: int, pan: float) -> None:
        with self._lock:
            self._ensure(harmonic_n)
            self._voices[harmonic_n].pan = max(-1.0, min(1.0, pan))
        self._notify()

    def set_phase(self, harmonic_n: int, phase_deg: float) -> None:
        """Set phase offset in degrees (0–360)."""
        with self._lock:
            self._ensure(harmonic_n)
            self._voices[harmonic_n].phase = math.radians(phase_deg % 360)
        self._notify()

    def set_params(self, harmonic_n: int, **kwargs) -> None:
        """Bulk update — accepts gain, pan, phase_deg."""
        with self._lock:
            self._ensure(harmonic_n)
            v = self._voices[harmonic_n]
            if "gain" in kwargs:
                v.gain = max(0.0, min(1.0, float(kwargs["gain"])))
            if "pan" in kwargs:
                v.pan = max(-1.0, min(1.0, float(kwargs["pan"])))
            if "phase_deg" in kwargs:
                v.phase = math.radians(float(kwargs["phase_deg"]) % 360)
        self._notify()

    def panic(self) -> None:
        """Reset all gains to 0.8, pan/phase to 0, mark inactive."""
        with self._lock:
            for v in self._voices.values():
                v.active = False
                v.gain = 0.8
                v.pan = 0.0
                v.phase = 0.0
            self._active_history.clear()
        self._notify()

    # ─── Snapshot accessors ───────────────────────────────────────────────────

    def get_snapshot(self) -> dict[int, VoiceParams]:
        """Active voices only — for audio callback."""
        with self._lock:
            return {k: v.copy() for k, v in self._voices.items()
                    if v.active and v.freq > 0}

    def get_all_snapshot(self) -> dict[int, VoiceParams]:
        """All known voices — for UI and MIDI slot mapping."""
        with self._lock:
            return {k: v.copy() for k, v in self._voices.items()}

    def to_dict(self) -> dict:
        """JSON-serializable state snapshot."""
        with self._lock:
            return {
                "f1": self.f1,
                "voices": {
                    str(k): {
                        "gain": v.gain,
                        "pan": v.pan,
                        "phase_deg": round(math.degrees(v.phase) % 360, 1),     # UI expects degrees
                        "active": v.active,
                        "freq": getattr(v, "freq", 0.0), # freq might not be set initially
                    }
                    for k, v in sorted(self._voices.items())
                },
            }
