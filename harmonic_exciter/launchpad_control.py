"""Launchpad Mini pad -> tine on/off selection with LED feedback."""

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


class LaunchpadControl:
    """Toggles tines on/off via Launchpad Mini pads with LED feedback.

    Pads 0-4 (bottom row, notes 11-15 in programmer mode) map to tines 0-4.
    Tap to activate, tap again to deactivate. LED mirrors active state.
    """

    def __init__(
        self,
        store: TineStateStore,
        port_pattern: str = config.LAUNCHPAD_PORT_PATTERN,
    ):
        if not HAS_MIDO:
            raise ImportError("mido is required for Launchpad control.")
        self._store = store
        self._port_pattern = port_pattern
        self._in_port: Optional[object] = None
        self._out_port: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # note -> tine index
        self._pad_to_tine: dict[int, int] = {
            note: i for i, note in enumerate(config.LAUNCHPAD_TINE_PADS)
        }

    # ---- Lifecycle -------------------------------------------------------

    def start(self) -> None:
        port_name = self._find_port()
        if not port_name:
            log.warning(
                "Launchpad not found (pattern=%r). "
                "Tine selection disabled — use store.tine_on/off() directly.",
                self._port_pattern,
            )
            return

        self._in_port = mido.open_input(port_name)
        try:
            self._out_port = mido.open_output(port_name)
        except Exception as e:
            log.warning("Could not open Launchpad output port: %s", e)

        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="exciter-launchpad", daemon=True
        )
        self._thread.start()
        self._refresh_leds()
        log.info("Launchpad control started on: %s", port_name)

    def stop(self) -> None:
        self._running = False
        self._clear_leds()
        if self._in_port:
            try:
                self._in_port.close()
            except Exception:
                pass
        if self._out_port:
            try:
                self._out_port.close()
            except Exception:
                pass

    # ---- MIDI loop -------------------------------------------------------

    def _find_port(self) -> Optional[str]:
        for name in mido.get_input_names():
            if self._port_pattern.lower() in name.lower():
                return name
        return None

    def _run(self) -> None:
        for msg in self._in_port:
            if not self._running:
                break
            self._handle(msg)

    def _handle(self, msg) -> None:
        if msg.type == "note_on" and msg.velocity > 0:
            tine = self._pad_to_tine.get(msg.note)
            if tine is not None:
                active = self._store.tine_toggle(tine)
                self._set_led(msg.note, active)
                log.debug("Pad %d -> tine %d %s", msg.note, tine, "ON" if active else "OFF")

    # ---- LED helpers -----------------------------------------------------

    def _set_led(self, note: int, active: bool) -> None:
        if self._out_port is None:
            return
        color = config.LED_COLOR_ACTIVE if active else config.LED_COLOR_INACTIVE
        try:
            self._out_port.send(mido.Message("note_on", note=note, velocity=color))
        except Exception as e:
            log.debug("LED send failed: %s", e)

    def _refresh_leds(self) -> None:
        """Sync all tine LEDs to current store state."""
        snap = self._store.get_all_snapshot()
        for note, tine in self._pad_to_tine.items():
            self._set_led(note, snap[tine].active)

    def _clear_leds(self) -> None:
        for note in self._pad_to_tine:
            self._set_led(note, False)

    def panic(self) -> None:
        """Panic: stop all tines and clear all LEDs."""
        self._store.panic()
        self._clear_leds()
        log.info("Launchpad: panic")
