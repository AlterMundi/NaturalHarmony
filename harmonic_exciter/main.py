"""Main entry point for the Harmonic Exciter."""

import argparse
import logging
import signal
import time

from .state import TineStateStore
from .beacon_client import BeaconClient
from .midi_control import Minilab3Control
from .launchpad_control import LaunchpadControl
from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("harmonic_exciter.main")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harmonic Exciter — MIDI control for electromagnetic kalimba tines"
    )
    parser.add_argument(
        "--beacon-host",
        default=config.BEACON_HOST,
        help=f"ESP32 beacon hostname or IP (default: {config.BEACON_HOST})",
    )
    parser.add_argument(
        "--beacon-port",
        type=int,
        default=config.BEACON_HTTP_PORT,
        help=f"ESP32 HTTP port (default: {config.BEACON_HTTP_PORT})",
    )
    parser.add_argument(
        "--fundamental",
        type=float,
        default=config.FUNDAMENTAL_HZ,
        help=f"Physical tuning fundamental Hz — informational only (default: {config.FUNDAMENTAL_HZ})",
    )
    parser.add_argument("--no-midi", action="store_true", help="Disable Minilab3 MIDI")
    parser.add_argument("--no-launchpad", action="store_true", help="Disable Launchpad")
    args = parser.parse_args()

    log.info("Starting Harmonic Exciter")
    log.info(
        "Physical tuning: fundamental=%.1f Hz, tines=%s Hz",
        args.fundamental,
        config.TINE_FREQS,
    )

    store = TineStateStore()
    client = BeaconClient(store, host=args.beacon_host, port=args.beacon_port)
    midi = Minilab3Control(store)
    launchpad = LaunchpadControl(store)

    def _shutdown(signum, frame):
        log.info("Signal %d — shutting down cleanly...", signum)
        store.panic()
        client.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    client.start()

    if not args.no_midi:
        midi.start()

    if not args.no_launchpad:
        launchpad.start()

    log.info(
        "Harmonic Exciter running. Beacon: http://%s:%d",
        args.beacon_host,
        args.beacon_port,
    )
    log.info("Use Launchpad pads 1-5 to activate tines. Minilab sliders/knobs adjust parameters.")
    log.info("Press Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        pass

    log.info("Shutting down...")
    if not args.no_midi:
        midi.stop()
    if not args.no_launchpad:
        launchpad.stop()
    client.stop()


if __name__ == "__main__":
    main()
