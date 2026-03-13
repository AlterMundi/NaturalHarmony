"""OSC receiver — listens to beacon broadcasts and direct shaper control."""

import logging
import socket
import threading
from typing import Optional

try:
    from pythonosc import dispatcher as osc_dispatcher
    from pythonosc import osc_server
    HAS_OSC = True
except ImportError:
    HAS_OSC = False

from .state import VoiceParameterStore

log = logging.getLogger(__name__)


class _ReusePortUDPServer(osc_server.BlockingOSCUDPServer if HAS_OSC else object):
    """BlockingOSCUDPServer with SO_REUSEPORT.

    Allows the shaper and the visualizer to co-listen on the same beacon
    broadcast port (9001) simultaneously on Linux.
    """
    def server_bind(self):
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            log.warning("SO_REUSEPORT unavailable — may conflict with visualizer on port 9001")
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


class ShaperOSCReceiver:
    """Dual-port OSC receiver.

    Port beacon_port (default 9001, SO_REUSEPORT):
        Receives /beacon/voice/on|off|freq  and /beacon/f1 from harmonic_beacon.

    Port shaper_port (default 9002):
        Receives direct /shaper/harmonic/<n>/gain|pan|phase  and /shaper/panic
        from experiment scripts or external automation.
    """

    def __init__(
        self,
        store: VoiceParameterStore,
        beacon_port: int = 9001,
        shaper_port: int = 9002,
        host: str = "0.0.0.0",
    ):
        if not HAS_OSC:
            raise ImportError("python-osc is required.")
        self._store = store
        self._beacon_port = beacon_port
        self._shaper_port = shaper_port
        self._host = host
        self._servers: list = []
        self._threads: list[threading.Thread] = []

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._start_beacon_listener()
        self._start_shaper_listener()

    def stop(self) -> None:
        for s in self._servers:
            try:
                s.shutdown()
            except Exception:
                pass

    # ─── Beacon listener (/beacon/*) ─────────────────────────────────────────

    def _start_beacon_listener(self) -> None:
        d = osc_dispatcher.Dispatcher()
        d.map("/beacon/voice/on", self._on_voice_on)
        d.map("/beacon/voice/off", self._on_voice_off)
        d.map("/beacon/voice/freq", self._on_voice_freq)
        d.map("/beacon/f1", self._on_f1)
        d.map("/beacon/panic", lambda *_: self._store.panic())
        d.set_default_handler(lambda *_: None)

        try:
            server = _ReusePortUDPServer((self._host, self._beacon_port), d)
        except OSError as exc:
            log.error("Could not bind beacon port %d: %s", self._beacon_port, exc)
            return

        self._servers.append(server)
        t = threading.Thread(target=server.serve_forever,
                             name="shaper-beacon-osc", daemon=True)
        t.start()
        self._threads.append(t)
        log.info("Beacon OSC listener on port %d", self._beacon_port)

    def _on_voice_on(self, addr, voice_id, freq, gain, source_note, harmonic_n=None, *_):
        """Accepts both 4-arg (legacy) and 5-arg beacon /beacon/voice/on payloads."""
        if harmonic_n is None:
            harmonic_n = int(source_note)
        else:
            harmonic_n = int(harmonic_n)
        self._store.voice_on(harmonic_n, int(voice_id), float(freq))
        log.debug("voice_on n=%d freq=%.2f", harmonic_n, freq)

    def _on_voice_off(self, addr, voice_id, *_):
        self._store.voice_off(int(voice_id))

    def _on_voice_freq(self, addr, voice_id, freq, *_):
        self._store.voice_freq(int(voice_id), float(freq))

    def _on_f1(self, addr, f1, *_):
        self._store.update_f1(float(f1))

    # ─── Direct shaper control (/shaper/*) ───────────────────────────────────

    def _start_shaper_listener(self) -> None:
        d = osc_dispatcher.Dispatcher()
        d.map("/shaper/harmonic/*/gain", self._on_gain)
        d.map("/shaper/harmonic/*/pan", self._on_pan)
        d.map("/shaper/harmonic/*/phase", self._on_phase)
        d.map("/shaper/panic", lambda *_: self._store.panic())
        d.set_default_handler(lambda *_: None)

        try:
            server = osc_server.BlockingOSCUDPServer((self._host, self._shaper_port), d)
        except OSError as exc:
            log.error("Could not bind shaper port %d: %s", self._shaper_port, exc)
            return

        self._servers.append(server)
        t = threading.Thread(target=server.serve_forever,
                             name="shaper-control-osc", daemon=True)
        t.start()
        self._threads.append(t)
        log.info("Shaper OSC control on port %d", self._shaper_port)

    @staticmethod
    def _parse_n(addr: str) -> Optional[int]:
        """Extract harmonic_n from /shaper/harmonic/<n>/param."""
        parts = addr.split("/")
        try:
            return int(parts[3])
        except (IndexError, ValueError):
            return None

    def _on_gain(self, addr, value, *_):
        n = self._parse_n(addr)
        if n is not None:
            self._store.set_gain(n, float(value))

    def _on_pan(self, addr, value, *_):
        n = self._parse_n(addr)
        if n is not None:
            self._store.set_pan(n, float(value))

    def _on_phase(self, addr, value, *_):
        """Accepts degrees."""
        n = self._parse_n(addr)
        if n is not None:
            self._store.set_phase(n, float(value))
