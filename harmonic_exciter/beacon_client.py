"""HTTP client: syncs TineStateStore state to the ESP32 beacon."""

import json
import logging
import queue
import threading
import urllib.request
import urllib.error
from typing import Optional

from .state import TineStateStore
from . import config

log = logging.getLogger(__name__)

_SENTINEL = object()


class BeaconClient:
    """Translates TineStateStore changes into HTTP commands to the ESP32.

    Strategy: on every state change, enqueue a sync.  The worker coalesces
    rapid changes (drains to latest) then executes:
      1. POST /api/stop         -- clears all beacon tines
      2. POST /api/play         -- re-drives all currently active tines

    Physical tines continue resonating naturally during the brief stop gap
    (~5-10ms on LAN), so the interruption is imperceptible.

    Phase (degrees 0-360) is sent per-tine in the play payload; the firmware
    applies it as LEDC hpoint so excitation cycles are offset in hardware.
    """

    def __init__(
        self,
        store: TineStateStore,
        host: str = config.BEACON_HOST,
        port: int = config.BEACON_HTTP_PORT,
    ):
        self._store = store
        self._base_url = f"http://{host}:{port}"
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_active_count: int = 0  # track to avoid spurious stops

    # ---- Lifecycle -------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="beacon-http", daemon=True
        )
        self._thread.start()
        # Wire store changes to our sync handler
        self._store._on_change = self._on_state_change
        log.info("BeaconClient started -> %s", self._base_url)
        self._check_connectivity()

    def stop(self) -> None:
        self._running = False
        self._queue.put(_SENTINEL)
        self._post_stop()  # silence beacon on shutdown

    # ---- State change hook -----------------------------------------------

    def _on_state_change(self) -> None:
        self._queue.put("sync")

    # ---- Worker thread ---------------------------------------------------

    def _run(self) -> None:
        while self._running:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            # Coalesce: drain any queued syncs, keep only latest
            while not self._queue.empty():
                try:
                    next_item = self._queue.get_nowait()
                    if next_item is _SENTINEL:
                        return
                except queue.Empty:
                    break
            self._sync()

    def _sync(self) -> None:
        snapshot = self._store.get_snapshot()   # active tines only
        master = self._store.get_master_duty()

        if not snapshot:
            # Only stop if we previously sent tines — avoids killing web-UI state
            if self._last_active_count > 0:
                self._post_stop()
                self._last_active_count = 0
            return

        self._post_stop()

        tines_payload = []
        for idx, params in sorted(snapshot.items()):
            vel = max(1, min(255, int(params.duty * master * 255)))
            tines_payload.append({
                "index": idx,
                "vel": vel,
                "dur": 0,           # infinite sustain
                "phase": params.phase,  # degrees 0-360, maps to LEDC hpoint
            })

        self._last_active_count = len(tines_payload)
        self._post("/api/play", {
            "mode": "sustain",
            "tines": tines_payload,
        })

    # ---- HTTP helpers ----------------------------------------------------

    def _post_stop(self) -> None:
        self._post("/api/stop", {})

    def _check_connectivity(self) -> None:
        url = self._base_url + "/api/version"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = resp.read().decode()
                log.info("Beacon reachable: GET /api/version -> %d %s", resp.status, body)
        except urllib.error.URLError as e:
            log.warning("Beacon NOT reachable at %s: %s", self._base_url, e.reason)
        except Exception as e:
            log.warning("Beacon connectivity check failed: %s", e)

    def _post(self, path: str, payload: dict) -> None:
        url = self._base_url + path
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                log.info("POST %s -> %d", path, resp.status)
        except urllib.error.URLError as e:
            log.warning("Beacon unreachable (%s): %s", path, e.reason)
        except Exception as e:
            log.warning("Beacon POST failed (%s): %s", path, e)
