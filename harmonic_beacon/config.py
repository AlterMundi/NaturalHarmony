"""Configuration constants for The Harmonic Beacon."""

# =============================================================================
# Base Frequency Settings
# =============================================================================

# Default fundamental frequency (f₁) in Hz
# 54 Hz is approximately between A1 and Bb1
DEFAULT_F1 = 65.0

# Range for f₁ modulation via MIDI CC (in Hz)
F1_MIN = 32.5   # A0
F1_MAX = 65.0   # A1 (Reduced range)

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
MIDI_PORT_PATTERN = None

# Secondary controller for modulation (e.g., Minilab3)
# Notes on this controller trigger modulation without producing sound
SECONDARY_MIDI_PORT_PATTERN = "Minilab"

# CC number for f₁ modulation (mod wheel = 1, common slider = 74)
F1_CC_NUMBER = 74

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

# CC number for multi-harmonic mode toggle (CC29)
# OFF = Single voice (lowest harmonic), ON = Multiple harmonics within tolerance
MULTI_HARMONIC_CC = 29

# CC number for max harmonics slider (CC90)
# When multi-harmonic mode is ON, this sets how many harmonics to play (1-16)
MAX_HARMONICS_CC = 90
DEFAULT_MAX_HARMONICS = 4  # Play up to 4 harmonics when enabled

# CC for Primary Voice Lock (CC28)
# OFF = Primary voice participates in mix, ON = Primary voice always 100%
PRIMARY_LOCK_CC = 28

# CC number for Natural Harmonics Mode toggle (CC30)
# OFF = Disable, ON = Play harmonics at original frequency
NATURAL_HARMONICS_CC = 30

# CC number for Natural Harmonics Level slider (CC92)
# Controls volume of natural harmonics (0-127)
NATURAL_LEVEL_CC = 92
DEFAULT_NATURAL_LEVEL = 64  # Mid-volume default

# CC for Harmonic Mix (CC89)
# 0 = Only Harmonics (if lock off), 127 = Only Primary (if lock off)
HARMONIC_MIX_CC = 89

# Maximum harmonic to search when finding matches
# Increased to 4096 to ensure full 20kHz coverage even for low f1 (e.g. 5Hz)
MAX_HARMONIC = 4096

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
# Pad Mode Configuration (Akai Force)
# =============================================================================

# Toggle Note for Pad Mode (Button/Note used to switch modes)
# Launchpad Side Button 1 (Note 8) is a good toggle if grid is 0-7
PAD_MODE_TOGGLE_NOTE = 8

# Anchor Note: The MIDI note number of the Bottom-Left Pad (Pad 1)
# Launchpad Programmer Mode starts at 0
PAD_ANCHOR_NOTE = 0
PAD_MODE_ENABLED_BY_DEFAULT = True
PANIC_NOTE = 111
PAD_FEEDBACK_COLOR_ON = 60     # Launchpad Green (60=Green High)

# Mapping Type: "LINEAR" (Sequential) or "LAUNCHPAD" (Row Stride 16)
PAD_MAP_TYPE = "LAUNCHPAD"

# Split Mode Configuration
SPLIT_MODE_ENABLED_BY_DEFAULT = False
SPLIT_MODE_TOGGLE_CC = 104  # Arrow Up / Top Button 1
PAD_FEEDBACK_COLOR_TOGGLE_ON = 21 # Orange (Low Velocity or Specific Color)

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
