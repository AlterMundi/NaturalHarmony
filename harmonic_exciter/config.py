"""Configuration for the Harmonic Exciter."""

# ---- Physical instrument ------------------------------------------------

# Fundamental is fixed by the physical tuning of the kalimba tines.
# The 50Hz tine is absent from the instrument; the 5 active tines start at H2.
FUNDAMENTAL_HZ = 50.0
TINE_FREQS = [100.0, 150.0, 200.0, 250.0, 300.0]  # Hz, index 0-4
TINE_COUNT = 5

# ---- Beacon network -----------------------------------------------------

BEACON_HOST = "beacon.local"
BEACON_HTTP_PORT = 80
OSC_PORT = 53280  # for future firmware OSC support

# ---- Minilab3 MIDI ------------------------------------------------------

MINILAB_PORT_PATTERN = "Minilab"

# Sliders 1-4 (factory MIDI1 preset) -> per-tine duty for tines 1-4
# Tine 0 (100Hz) is the reference and is not mapped to any slider.
MINILAB_SLIDER_CCS = [14, 15, 30, 31]

# Top knobs 1-4 -> per-tine phase (0-360 deg) for tines 1-4
MINILAB_PHASE_CCS = [86, 87, 89, 90]

# Pad 4 -> panic / stop all
MINILAB_PANIC_PAD = 39

# ---- Launchpad ----------------------------------------------------------

LAUNCHPAD_PORT_PATTERN = "Launchpad"

# ---- Defaults -----------------------------------------------------------

DEFAULT_DUTY = 0.8        # normalized 0-1, applied to active tines
DEFAULT_PHASE = 0.0       # degrees
DEFAULT_MASTER_DUTY = 1.0
DEFAULT_PLUCK_MS = 30     # milliseconds for a pluck pulse
