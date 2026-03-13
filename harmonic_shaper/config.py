"""Configuration for the Harmonic Shaper."""

# ─── Audio ────────────────────────────────────────────────────────────────────

AUDIO_SAMPLE_RATE = 44100
AUDIO_BLOCK_SIZE = 256
AUDIO_DEVICE = None       # None = system default; set to device name/index to override

# ─── OSC ──────────────────────────────────────────────────────────────────────

# Beacon broadcast port — shaper co-listens here (SO_REUSEPORT alongside visualizer)
BEACON_BROADCAST_PORT = 9001

# Direct shaper OSC control port
SHAPER_OSC_PORT = 9002

OSC_HOST = "0.0.0.0"

# ─── HTTP / WebSocket API ─────────────────────────────────────────────────────

API_HOST = "127.0.0.1"
API_PORT = 8080

# ─── Minilab3 MIDI ────────────────────────────────────────────────────────────

MINILAB_PORT_PATTERN = "Minilab"

# Sliders 1-4 (MIDI1 factory preset)
MINILAB_SLIDER_CCS = [14, 15, 30, 31]

# Knobs 1-4 (Top row)
MINILAB_PAN_CCS = [86, 87, 89, 90]

# Knobs 5-8 (Bottom row)
MINILAB_PHASE_CCS = [110, 111, 116, 117]

# Pad 4 -> Panic is still used
MINILAB_PANIC_PAD = 39

# ─── Experiment / Dataset ─────────────────────────────────────────────────────

DATASET_DIR = "datasets"
DATASET_LOG_INTERVAL_S = 0.1   # 10 Hz snapshot rate

# ─── Harmonic beacon defaults (should match harmonic_beacon/config.py) ─────────

DEFAULT_F1 = 65.0
