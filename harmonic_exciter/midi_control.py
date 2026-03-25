"""Minilab3 MIDI -> exciter parameter control."""

import logging
import threading
from typing import Optional

try:
    import mido
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False

from .state import TineStateStore
from . import config

log = logging.getLogger(__name__)


class Minilab3Control:
    """Maps Minilab3 MIDI sliders/knobs/pads to TineStateStore parameters.

    Hardware mapping:
        Modwheel (CC1)      : master duty
        Sliders 1-4         : duty for tines 1-4  (tine 0 = 100Hz reference, unmapped)
        Top knobs 1-4       : phase for tines 1-4 (0-360 deg)
        Pad 4 (note 39)     : panic / stop all
    """

    def __init__(
        self,
        store: TineStateStore,
        port_pattern: str = config.MINILAB_PORT_PATTERN,
    ):
        if not HAS_MIDO:
            raise ImportError("mido is required for MIDI control.")
        self._store = store
        self._port_pattern = port_pattern
        self._port: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # CC -> tine index dicts (built from config lists)
        self._slider_to_tine: dict[int, int] = {
            cc: i + 1 for i, cc in enumerate(config.MINILAB_SLIDER_CCS)
        }
        self._phase_to_tine: dict[int, int] = {
            cc: i + 1 for i, cc in enumerate(config.MINILAB_PHASE_CCS)
        }

    # ---- Lifecycle -------------------------------------------------------

    def start(self) -> None:
        all_ports = mido.get_input_names()
        log.info("MIDI input ports: %s", all_ports)
        port_name = self._find_port()
        if not port_name:
            log.warning(
                "Minilab3 not found (pattern=%r). "
                "MIDI control disabled — exciter still works via Launchpad.",
                self._port_pattern,
            )
            return
        self._port = mido.open_input(port_name)
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="exciter-midi", daemon=True
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

    # ---- MIDI loop -------------------------------------------------------

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

        # Modwheel -> master duty
        if cc == 1:
            self._store.set_master_duty(norm)
            log.debug("Modwheel -> master duty=%.3f", norm)
            return

        # Sliders -> per-tine duty
        tine = self._slider_to_tine.get(cc)
        if tine is not None:
            self._store.set_duty(tine, norm)
            log.debug("Slider -> tine %d duty=%.3f (cc=%d)", tine, norm, cc)
            return

        # Top knobs -> per-tine phase
        tine = self._phase_to_tine.get(cc)
        if tine is not None:
            phase = norm * 360.0
            self._store.set_phase(tine, phase)
            log.debug("Knob -> tine %d phase=%.1f deg (cc=%d)", tine, phase, cc)
            return

        log.debug("CC unmatched: cc=%d val=%d", cc, value)

    def _handle_pad(self, note: int) -> None:
        if note == config.MINILAB_PANIC_PAD:
            log.info("Minilab3: panic")
            self._store.panic()
