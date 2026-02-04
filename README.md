# The Harmonic Beacon 🎵

A Python MIDI middleware that maps a standard 12-key controller to the **Natural Harmonic Series**, creating a dual-voice "Harmonic Beacon" effect.

## Overview

The Harmonic Beacon transforms your MIDI keyboard into a microtonal instrument based on the natural harmonic series. Each key triggers **two voices**:

1. **Beacon Voice** — The raw harmonic frequency (f₁ × n)
2. **Playable Voice** — The octave-reduced harmonic, transposed to your playing range

This creates a shimmering, harmonically pure sound that differs from standard 12-tone equal temperament.

## Harmonic Mapping

| Key | Harmonic (n) | Ratio | Interval |
|-----|--------------|-------|----------|
| C   | 1  | 1/1   | Fundamental |
| C#  | 17 | 17/16 | Minor Second |
| D   | 9  | 9/8   | Major Second |
| Eb  | 19 | 19/16 | Harmonic m3 |
| E   | 5  | 5/4   | Major Third |
| F   | 21 | 21/16 | Narrow Fourth |
| F#  | 11 | 11/8  | Mystic Tritone |
| G   | 3  | 3/2   | Perfect Fifth |
| Ab  | 13 | 13/8  | Harmonic m6 |
| A   | 27 | 27/16 | Major Sixth |
| Bb  | 7  | 7/4   | Harmonic Seventh |
| B   | 15 | 15/8  | Major Seventh |

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/NaturalHarmony.git
cd NaturalHarmony

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- **mido** — MIDI message handling
- **python-rtmidi** — Real-time MIDI I/O
- **pyliblo3** — OSC communication with Surge XT

## Usage

### Basic Usage

```bash
# Run with mock OSC (for testing without Surge XT)
python -m harmonic_beacon.main --mock

# Run with real OSC to Surge XT
python -m harmonic_beacon.main --broadcast --mpe

# Run the 3D Visualizer
python -m harmonic_visualizer.main --3d
```

### Hardware Support

- **Arturia KeyLab 61 MkII** (Keyboard Mode)
- **Novation Launchpad Mini** (Pad Mode)

### Modes

#### Keyboard Mode
Maps the 12-semitone octave to specific harmonics based on intervals (see table below).

#### Pad Mode (Launchpad Mini)
Maps the 8x8 pad grid directly to Harmonics 1-64.
- **Toggle**: Top-Right Side Button (Note 8).
- **Panic**: CC 111 or Note 111 (Top Right Side Button on some layouts).
- **Layout**: Harmonic 1 is at the Bottom-Left.
- **Feedback**: Pads light up Green (High Velocity) when active.

### Command Line Options

```
--mock          Use mock OSC sender (logs output instead of sending)
--quiet         Reduce output verbosity
--list-ports    List available MIDI input ports and exit
--f1 FREQ       Set initial base frequency in Hz (default: 54.0)
```

### List MIDI Ports

```bash
python -m harmonic_beacon.main --list-ports
```

## Configuration

Edit `harmonic_beacon/config.py` to customize:

- **DEFAULT_F1** — Base frequency (default: 54.0 Hz)
- **F1_MIN / F1_MAX** — Range for CC modulation
- **MIDI_PORT_PATTERN** — Substring to match your controller
- **F1_CC_NUMBER** — CC number for f₁ modulation (default: 1 = mod wheel)
- **OSC_HOST / OSC_PORT** — Surge XT OSC target

## Surge XT Setup

1. Open Surge XT
2. Enable OSC input (Menu → Audio/MIDI → OSC)
3. Set the OSC port to match `config.OSC_PORT` (default: 9000)

## f₁ Modulation

Use your controller's mod wheel (CC 1) or configure a slider to smoothly shift the base frequency. All active notes will follow the modulation in real-time, creating evolving harmonic relationships.

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Project Structure

```
harmonic_beacon/
├── __init__.py      # Package init
├── config.py        # Configuration constants
├── harmonics.py     # Harmonic math and mappings
├── midi_handler.py  # MIDI input processing
├── osc_sender.py    # OSC output to Surge XT
├── polyphony.py     # Voice tracking
└── main.py          # Entry point and event loop
```

## License

MIT License — See LICENSE file for details.

## Acknowledgments

Based on the mathematical beauty of the natural harmonic series and the pioneering work in just intonation and spectral music.
