"""Main entry point for the Harmonic Shaper."""

import argparse
import logging
import time

from .state import VoiceParameterStore
from .audio_engine import AudioEngine
from .osc_receiver import ShaperOSCReceiver
from .midi_control import Minilab3Control
from .logger import DatasetLogger
from .api import run_server
from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("harmonic_shaper.main")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harmonic Shaper")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices")
    parser.add_argument("--device", type=str, help="Audio device ID or substring")
    parser.add_argument("--no-midi", action="store_true", help="Disable Minilab3 MIDI")
    parser.add_argument("--no-osc", action="store_true", help="Disable OSC receivers")
    parser.add_argument("--no-ui", action="store_true", help="Disable Web/API server")
    args = parser.parse_args()

    if args.list_devices:
        print(AudioEngine.list_devices())
        return

    log.info("Starting Harmonic Shaper...")

    store = VoiceParameterStore()
    dataset_logger = DatasetLogger(store, log_dir=config.DATASET_DIR, interval_s=config.DATASET_LOG_INTERVAL_S)
    audio = AudioEngine(store,
                        sample_rate=config.AUDIO_SAMPLE_RATE,
                        block_size=config.AUDIO_BLOCK_SIZE,
                        device=args.device or config.AUDIO_DEVICE)
    osc = ShaperOSCReceiver(store,
                            beacon_port=config.BEACON_BROADCAST_PORT,
                            shaper_port=config.SHAPER_OSC_PORT,
                            host=config.OSC_HOST)
    midi = Minilab3Control(store, port_pattern=config.MINILAB_PORT_PATTERN)

    audio.start()
    
    if not args.no_osc:
        osc.start()
        
    if not args.no_midi:
        midi.start()

    log.info("Harmonic Shaper running.")

    if not args.no_ui:
        # Run FastAPI under uvicorn (blocking)
        log.info("Starting Web UI / API on http://%s:%d", config.API_HOST, config.API_PORT)
        try:
            run_server(store, dataset_logger, host=config.API_HOST, port=config.API_PORT)
        except KeyboardInterrupt:
            pass
    else:
        # No UI, just sleep loop
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

    log.info("Shutting down...")
    if not args.no_midi:
        midi.stop()
    if not args.no_osc:
        osc.stop()
    audio.stop()
    dataset_logger.stop_session()


if __name__ == "__main__":
    main()
