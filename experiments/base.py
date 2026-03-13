"""Experiment base class and HTTP client helper."""

import time
import math
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8080"


class ShaperClient:
    """Thin HTTP wrapper for controlling the shaper from experiment scripts."""

    def __init__(self, base_url: str = BASE_URL):
        self.base = base_url.rstrip("/")

    def set_gain(self, n: int, gain: float):
        self._put(n, gain=gain)

    def set_pan(self, n: int, pan: float):
        self._put(n, pan=pan)

    def set_phase(self, n: int, phase_deg: float):
        self._put(n, phase_deg=phase_deg)

    def set_params(self, n: int, **kwargs):
        self._put(n, **kwargs)

    def panic(self):
        requests.post(f"{self.base}/api/panic")

    def state(self) -> dict:
        return requests.get(f"{self.base}/api/state").json()

    def start_session(self, experiment_id: str, metadata: Optional[dict] = None) -> str:
        r = requests.post(f"{self.base}/api/session/start",
                         json={"experiment_id": experiment_id, "metadata": metadata or {}})
        return r.json().get("session_id", "")

    def stop_session(self):
        requests.post(f"{self.base}/api/session/stop")

    def _put(self, n: int, **kwargs):
        requests.put(f"{self.base}/api/harmonic/{n}", json=kwargs)


class Experiment:
    """Base class for parameterized cymatic experiments.

    Subclass and implement run(). Use self.client to control the shaper.
    The session is automatically started/stopped around run().

    Example:
        class MyExp(Experiment):
            def run(self):
                for n, phase in enumerate(range(0, 360, 10)):
                    self.client.set_phase(n+1, phase)
                    self.wait(0.5)
    """

    name: str = "unnamed"
    description: str = ""

    def __init__(self, base_url: str = BASE_URL):
        self.client = ShaperClient(base_url)
        self._start_time: Optional[float] = None

    def wait(self, seconds: float):
        """Sleep for seconds, relative to experiment start."""
        time.sleep(seconds)

    def elapsed(self) -> float:
        """Seconds since experiment start."""
        return time.monotonic() - (self._start_time or time.monotonic())

    def lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation."""
        return a + (b - a) * max(0.0, min(1.0, t))

    def run(self):
        """Override in subclasses."""
        raise NotImplementedError

    def execute(self, record: bool = True):
        """Run the experiment with optional dataset recording."""
        log.info("Starting experiment: %s", self.name)
        session_id = None
        if record:
            session_id = self.client.start_session(
                experiment_id=self.name,
                metadata={"description": self.description},
            )
            log.info("Recording session: %s", session_id)

        self._start_time = time.monotonic()
        try:
            self.run()
        finally:
            if record:
                self.client.stop_session()
        log.info("Experiment complete: %s", self.name)
        return session_id
