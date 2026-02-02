"""Configuration for the Harmonic Visualizer."""

# OSC settings
OSC_HOST = "127.0.0.1"
OSC_PORT = 9001  # Receive from Harmonic Beacon broadcast

# Window settings
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_TITLE = "Harmonic Visualizer"
FPS = 60

# Keyboard settings
# KeyLab MKII 61: 61 keys, ±3 octaves transpose = full MIDI range accessible
KEYBOARD_KEYS = 61
KEYBOARD_LOWEST_NOTE = 36  # C2 (default, adjustable with transpose)
KEYBOARD_TRANSPOSE_RANGE = 3  # ±3 octaves

# Colors (RGB)
COLOR_BACKGROUND = (15, 15, 25)
COLOR_SPINE_INACTIVE = (50, 50, 70)
COLOR_SPINE_ACTIVE = (100, 200, 255)
COLOR_SPINE_GLOW = (150, 230, 255)
COLOR_KEY_INACTIVE = (40, 40, 50)
COLOR_KEY_WHITE = (220, 220, 230)
COLOR_KEY_BLACK = (30, 30, 40)
COLOR_KEY_PRESSED = (100, 200, 255)
COLOR_ENERGY_LINE = (100, 200, 255, 128)
COLOR_CC_BAR = (30, 30, 45)
COLOR_TEXT = (200, 200, 210)

# Layout proportions
SPINE_WIDTH_RATIO = 0.35  # Left panel
KEYBOARD_WIDTH_RATIO = 0.65  # Right panel
CC_BAR_HEIGHT = 60  # Bottom bar height

# Harmonic spine settings
MAX_HARMONICS_DISPLAY = 24  # How many harmonics to show
VERTEBRA_HEIGHT_BASE = 30  # Base height for n=1
VERTEBRA_HEIGHT_MIN = 12  # Minimum height for high harmonics

# Animation settings
GLOW_FADE_SPEED = 5.0  # How fast glow fades after note off
ENERGY_LINE_WIDTH = 2
