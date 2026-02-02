"""Configuration constants for The Harmonic Beacon."""

# =============================================================================
# Base Frequency Settings
# =============================================================================

# Default fundamental frequency (f₁) in Hz
# 54 Hz is approximately between A1 and Bb1
DEFAULT_F1 = 54.0

# Range for f₁ modulation via MIDI CC (in Hz)
F1_MIN = 27.5   # A0
F1_MAX = 220.0  # A3

# Smoothing rate for f₁ interpolation (0.0 to 1.0)
# Lower = smoother but slower response
F1_SMOOTHING_RATE = 0.1

# =============================================================================
# Keyboard Mapping
# =============================================================================

# Anchor key: MIDI note number that represents f₁ (the fundamental)
# C1 = 24 (standard), but adjust based on your keyboard's lowest C
ANCHOR_MIDI_NOTE = 24  # C1 = f₁

# Keyboard range (standard 88-key piano: A0=21 to C8=108)
# Adjust for your controller (e.g., 61-key often starts at C2=36)
LOWEST_MIDI_NOTE = 21   # A0
HIGHEST_MIDI_NOTE = 108 # C8

# =============================================================================
# MIDI Configuration
# =============================================================================

# Pattern to match MIDI input port name (case-insensitive substring match)
# Set to None to use the first available port
MIDI_PORT_PATTERN = "KeyLab"

# CC number for f₁ modulation (mod wheel = 1, common slider = 74)
F1_CC_NUMBER = 1

# CC number for aftertouch mode toggle (KeyLab toggle button 1 = CC22)
# OFF = f₁ Center mode, ON = Key Anchor mode
AFTERTOUCH_MODE_CC = 22

# CC number for tolerance slider (KeyLab slider 1 = CC67)
# Maps 1-127 to TOLERANCE_MIN-TOLERANCE_MAX cents
TOLERANCE_CC = 67
TOLERANCE_MIN = 1.0    # cents
TOLERANCE_MAX = 50.0   # cents
DEFAULT_TOLERANCE = 25.0  # cents

# CC number for LFO rate slider (KeyLab slider 2 = CC68)
# Maps 1-127 to LFO_RATE_MIN-LFO_RATE_MAX Hz
LFO_RATE_CC = 68
LFO_RATE_MIN = 0.1    # Hz
LFO_RATE_MAX = 10.0   # Hz
DEFAULT_LFO_RATE = 1.0  # Hz

# CC number for vibrato mode toggle (KeyLab toggle button 2 = CC23)
# OFF = Smooth interpolation, ON = Stepped (discrete jumps)
VIBRATO_MODE_CC = 23

# CC number for aftertouch enable toggle (CC30)
# OFF = Aftertouch disabled, ON = Aftertouch enabled
AFTERTOUCH_ENABLE_CC = 30

# CC number for aftertouch pressure threshold slider (CC92)
# Maps 0-127 to 0-127 pressure threshold
AFTERTOUCH_THRESHOLD_CC = 92
DEFAULT_AFTERTOUCH_THRESHOLD = 64

# Maximum harmonic to search when finding matches
MAX_HARMONIC = 128

# =============================================================================
# OSC Configuration (Surge XT)
# =============================================================================

# Surge XT OSC target
OSC_HOST = "127.0.0.1"
#OSC_PORT = 9000
OSC_PORT = 53280

# Visualizer broadcast port (separate from Surge XT)
BROADCAST_PORT = 9001

# OSC address patterns for Surge XT
# Note: These may need adjustment based on Surge XT's actual OSC implementation
OSC_NOTE_ON = "/surge/noteon"
OSC_NOTE_OFF = "/surge/noteoff"
OSC_PARAMETER = "/surge/param"

# =============================================================================
# Voice Management
# =============================================================================

# Maximum simultaneous voices (Beacon + Playable = 2 per note)
MAX_VOICES = 32



# =============================================================================
# Performance
# =============================================================================

# Main loop update rate (Hz)
UPDATE_RATE = 1000

# MIDI polling interval (seconds)
MIDI_POLL_INTERVAL = 0.001
