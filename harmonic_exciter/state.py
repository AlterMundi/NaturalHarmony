"""Thread-safe tine parameter store for the Harmonic Exciter."""

import threading
from copy import copy
from dataclasses import dataclass
from typing import Callable, Optional

from . import config


@dataclass
class TineParams:
    """Parameters for a single physical tine."""
    tine_idx: int
    freq: float    # Hz — fixed by physical tuning, from config.TINE_FREQS
    duty: float    # 0.0–1.0  (excitation strength)
    phase: float   # 0.0–360.0 degrees (relative phase of PWM, via LEDC hpoint)
    active: bool   # whether the tine is currently being driven

    def copy(self) -> "TineParams":
        return copy(self)

    def to_dict(self) -> dict:
        return {
            "tine_idx": self.tine_idx,
            "freq": self.freq,
            "duty": round(self.duty, 4),
            "phase_deg": round(self.phase, 1),
            "active": self.active,
        }


class TineStateStore:
    """Thread-safe store for per-tine exciter parameters.

    Indexed by tine index (0-4).  Control surfaces (Minilab3 sliders/knobs,
    modwheel) write duty and phase.  The Launchpad writes active state.
    The BeaconClient reads via get_snapshot() and drives the ESP32 accordingly.
    """

    def __init__(self, on_change: Optional[Callable[[], None]] = None):
        self._lock = threading.RLock()
        self._tines: dict[int, TineParams] = {
            i: TineParams(
                tine_idx=i,
                freq=config.TINE_FREQS[i],
                duty=config.DEFAULT_DUTY,
                phase=config.DEFAULT_PHASE,
                active=False,
            )
            for i in range(config.TINE_COUNT)
        }
        self._master_duty: float = config.DEFAULT_MASTER_DUTY
        self._on_change = on_change

    # ---- Internal -------------------------------------------------------

    def _notify(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    # ---- Launchpad-driven activation ------------------------------------

    def tine_on(self, idx: int) -> None:
        if idx < 0 or idx >= config.TINE_COUNT:
            return
        with self._lock:
            self._tines[idx].active = True
        self._notify()

    def tine_off(self, idx: int) -> None:
        if idx < 0 or idx >= config.TINE_COUNT:
            return
        with self._lock:
            self._tines[idx].active = False
        self._notify()

    def tine_toggle(self, idx: int) -> bool:
        """Toggle tine active state. Returns new active value."""
        if idx < 0 or idx >= config.TINE_COUNT:
            return False
        with self._lock:
            new_state = not self._tines[idx].active
            self._tines[idx].active = new_state
        self._notify()
        return new_state

    # ---- Minilab3 parameter control -------------------------------------

    def set_duty(self, idx: int, duty: float) -> None:
        if idx < 0 or idx >= config.TINE_COUNT:
            return
        with self._lock:
            self._tines[idx].duty = max(0.0, min(1.0, duty))
        self._notify()

    def set_phase(self, idx: int, phase_deg: float) -> None:
        if idx < 0 or idx >= config.TINE_COUNT:
            return
        with self._lock:
            self._tines[idx].phase = phase_deg % 360.0
        self._notify()

    def set_master_duty(self, duty: float) -> None:
        self._master_duty = max(0.0, min(1.0, duty))
        self._notify()

    def get_master_duty(self) -> float:
        return self._master_duty

    # ---- Panic ----------------------------------------------------------

    def panic(self) -> None:
        """Stop all tines and reset duty/phase to defaults."""
        with self._lock:
            for t in self._tines.values():
                t.active = False
                t.duty = config.DEFAULT_DUTY
                t.phase = config.DEFAULT_PHASE
            self._master_duty = config.DEFAULT_MASTER_DUTY
        self._notify()

    # ---- Snapshot accessors ---------------------------------------------

    def get_snapshot(self) -> dict[int, TineParams]:
        """Active tines only — for the BeaconClient."""
        with self._lock:
            return {i: t.copy() for i, t in self._tines.items() if t.active}

    def get_all_snapshot(self) -> dict[int, TineParams]:
        """All 5 tines — for UI and MIDI slot mapping."""
        with self._lock:
            return {i: t.copy() for i, t in self._tines.items()}

    def to_dict(self) -> dict:
        """JSON-serializable state snapshot."""
        with self._lock:
            return {
                "master_duty": self._master_duty,
                "tines": {
                    str(i): t.to_dict()
                    for i, t in sorted(self._tines.items())
                },
            }
