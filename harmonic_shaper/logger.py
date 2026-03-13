"""Dataset logger — timestamped CSV snapshots of shaper state."""

import csv
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .state import VoiceParameterStore

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "session_id", "experiment_id", "timestamp_ns",
    "harmonic_n", "freq_hz", "gain", "pan", "phase_deg", "active",
]


class DatasetLogger:
    """Periodically snapshots VoiceParameterStore into a CSV file.

    Usage:
        logger = DatasetLogger(store, log_dir="datasets")
        logger.start_session(experiment_id="phase_sweep_01")
        # ... run experiment ...
        logger.stop_session()

    Output: datasets/<session_id>/log.csv
    Metadata: datasets/<session_id>/meta.json
    """

    def __init__(
        self,
        store: VoiceParameterStore,
        log_dir: str = "datasets",
        interval_s: float = 0.1,
    ):
        self._store = store
        self._log_dir = Path(log_dir)
        self._interval = interval_s
        self._session_id: Optional[str] = None
        self._experiment_id: Optional[str] = None
        self._csv_path: Optional[Path] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ─── Session lifecycle ────────────────────────────────────────────────────

    def start_session(
        self,
        experiment_id: str = "manual",
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        if self._running:
            self.stop_session()

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._session_id = session_id or f"session_{ts}"
        self._experiment_id = experiment_id

        session_dir = self._log_dir / self._session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        self._csv_path = session_dir / "log.csv"

        # Write metadata
        import json
        meta = {
            "session_id": self._session_id,
            "experiment_id": experiment_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "f1": self._store.f1,
            "interval_s": self._interval,
        }
        if metadata:
            meta.update(metadata)
        (session_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="shaper-logger", daemon=True
        )
        self._thread.start()
        log.info("Dataset logger started: %s (experiment=%s)", self._csv_path, experiment_id)
        return self._session_id

    def stop_session(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        log.info("Dataset logger stopped: session=%s", self._session_id)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        with open(self._csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            while self._running:
                ts_ns = time.monotonic_ns()
                snapshot = self._store.get_all_snapshot()
                for n, params in sorted(snapshot.items()):
                    writer.writerow({
                        "session_id":    self._session_id,
                        "experiment_id": self._experiment_id,
                        "timestamp_ns":  ts_ns,
                        "harmonic_n":    n,
                        "freq_hz":       round(params.freq, 4),
                        "gain":          round(params.gain, 4),
                        "pan":           round(params.pan, 4),
                        "phase_deg":     round(math.degrees(params.phase) % 360, 2),
                        "active":        int(params.active),
                    })
                f.flush()
                time.sleep(self._interval)
