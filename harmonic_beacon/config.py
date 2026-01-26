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

# =============================================================================
# OSC Configuration (Surge XT)
# =============================================================================

# Surge XT OSC target
OSC_HOST = "127.0.0.1"
#OSC_PORT = 9000
OSC_PORT = 53280

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

# Target octave for "playable" voice (MIDI octave, where C4 = octave 4)
PLAYABLE_TARGET_OCTAVE = 4

# =============================================================================
# Performance
# =============================================================================

# Main loop update rate (Hz)
UPDATE_RATE = 1000

# MIDI polling interval (seconds)
MIDI_POLL_INTERVAL = 0.001
