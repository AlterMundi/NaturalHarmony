"""Minilab3 MIDI → shaper parameter control."""

import logging
import threading
from enum import Enum
from typing import Optional

try:
    import mido
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False

from .state import VoiceParameterStore
from . import config

log = logging.getLogger(__name__)


class Minilab3Control:
    """Maps Minilab3 MIDI encoders and faders directly to shaper parameters for 4 upper voices.

    Hardware mapping:
        Sliders 1-4 : Gain for harmonics 2-5
        Knobs 1-4   : Pan for harmonics 2-5
        Knobs 5-8   : Phase for harmonics 2-5
        Pad 4       : Panic (reset all params)

    Harmonic slots: the 4 upper active harmonic_n values. 
    The lowest active harmonic (n=1) acts as an untweaked reference.
    """

    def __init__(
        self,
        store: VoiceParameterStore,
        port_pattern: str = config.MINILAB_PORT_PATTERN,
    ):
        if not HAS_MIDO:
            raise ImportError("mido is required for MIDI control.")
        self._store = store
        self._port_pattern = port_pattern
        self._port: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # HW mappings
        self._slider_to_slot: dict[int, int] = {
            cc: i for i, cc in enumerate(config.MINILAB_SLIDER_CCS)
        }
        self._pan_to_slot: dict[int, int] = {
            cc: i for i, cc in enumerate(config.MINILAB_PAN_CCS)
        }
        self._phase_to_slot: dict[int, int] = {
            cc: i for i, cc in enumerate(config.MINILAB_PHASE_CCS)
        }

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        port_name = self._find_port()
        if not port_name:
            log.warning(
                "Minilab3 not found (pattern=%r). "
                "MIDI control disabled — shaper still works via web UI and OSC.",
                self._port_pattern,
            )
            return
        self._port = mido.open_input(port_name)
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="shaper-midi", daemon=True
        )
        self._thread.start()
        log.info("Minilab3 control started on: %s", port_name)

    def stop(self) -> None:
        self._running = False
        if self._port:
            try:
                self._port.close()
            except Exception:
                pass

    # ─── MIDI loop ────────────────────────────────────────────────────────────

    def _find_port(self) -> Optional[str]:
        for name in mido.get_input_names():
            if self._port_pattern.lower() in name.lower():
                return name
        return None

    def _run(self) -> None:
        for msg in self._port:
            if not self._running:
                break
            self._handle(msg)

    def _handle(self, msg) -> None:
        if msg.type == "control_change":
            self._handle_cc(msg.control, msg.value)
        elif msg.type in ("note_on", "note_off") and msg.velocity > 0:
            self._handle_pad(msg.note)

    def _handle_cc(self, cc: int, value: int) -> None:
        norm = value / 127.0

        # Modwheel — master gain
        if cc == 1:
            self._store.set_master_gain(norm)
            log.debug("Modwheel → master gain=%.3f (cc=%d val=%d)", norm, cc, value)
            return

        matched = (
            cc in self._slider_to_slot
            or cc in self._pan_to_slot
            or cc in self._phase_to_slot
        )
        if not matched:
            log.info("CC unmatched — cc=%d val=%d (add to config if this is a control)", cc, value)

        # Sliders (Gain)
        slider_slot = self._slider_to_slot.get(cc)
        if slider_slot is not None:
            n = self._slot_to_harmonic_n(slider_slot)
            if n is not None:
                self._store.set_gain(n, norm)
                log.debug("Slider → H%d gain=%.3f (cc=%d val=%d)", n, norm, cc, value)
            return

        # Top Knobs (Pan)
        pan_slot = self._pan_to_slot.get(cc)
        if pan_slot is not None:
            n = self._slot_to_harmonic_n(pan_slot)
            if n is not None:
                pan_val = norm * 2.0 - 1.0
                self._store.set_pan(n, pan_val)
                log.debug("Knob Top → H%d pan=%.3f (cc=%d val=%d)", n, pan_val, cc, value)
            return

        # Bottom Knobs (Phase)
        phase_slot = self._phase_to_slot.get(cc)
        if phase_slot is not None:
            n = self._slot_to_harmonic_n(phase_slot)
            if n is not None:
                phase_val = norm * 360.0
                self._store.set_phase(n, phase_val)
                log.debug("Knob Bottom → H%d phase=%.3f (cc=%d val=%d)", n, phase_val, cc, value)
            return

    def _handle_pad(self, note: int) -> None:
        if note == config.MINILAB_PANIC_PAD:
            log.info("Minilab3: panic")
            self._store.panic()
            return

    def _slot_to_harmonic_n(self, slot: int) -> Optional[int]:
        """Map slot index (0-3) to the (slot+1)-th lowest *active* harmonic_n.
        The lowest active harmonic (index 0) is reserved as the acoustic reference."""
        snap = self._store.get_snapshot()   # active + freq>0 only
        active = sorted(snap.keys())
        if slot + 1 < len(active):
            return active[slot + 1]
        log.debug("Slot %d out of range — only %d active voice(s)", slot, len(active))
        return None
