# Natural Harmony 🎵

**MIDI middleware and visualizer for playing the Natural Harmonic Series**

Natural Harmony transforms your MIDI keyboard or pad controller into a microtonal instrument based on the natural harmonic series, with real-time visualization of active harmonics.

## Overview

Natural Harmony consists of two components:

1. **Harmonic Beacon** — MIDI processor that maps keys to natural harmonic frequencies
2. **Harmonic Visualizer** — Real-time display of active harmonics and keyboard state

The system uses **Optimized Chromatic** mapping, where each semitone maps to carefully chosen harmonic ratios that balance simplicity with musical intervals.

## Quick Start

```bash
# Clone and install
git clone https://github.com/<your-org-or-user>/NaturalHarmony.git
cd NaturalHarmony
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the Harmonic Beacon (MIDI processor)
python -m harmonic_beacon.main

# In another terminal, run the visualizer
source venv/bin/activate
python -m harmonic_visualizer.main
```

## Features

### Harmonic Beacon

- **Two Operating Modes:**
  - **Keyboard Mode**: Chromatic mapping with optimized harmonic prototypes
  - **Pad Mode** (startup default): Direct 1:1 mapping of 64 pads to harmonics 1-64

- **Stacking Mode** (CC22): Play both transposed (pitch-correct) and natural (spectral) frequencies
- **Split Mode** (Pad Mode only, CC104): Lower 4 rows momentary, upper 4 rows toggle/latch
- **Dynamic f₁ modulation** (CC74): Shift entire harmonic series in real-time
- **Modulation Controller**: Play notes on secondary MIDI device to retune on-the-fly
- **LFO Chorus**: Smooth vibrato effect sweeping through matching harmonics
- **MPE Output**: Optional MIDI Polyphonic Expression support

### Harmonic Visualizer

- **Harmonic Spine**: Vertical display of active harmonic positions with glowing indicators
- **Virtual Keyboard**: Shows pressed keys with highlighting
- **Energy Lines**: Connect active keys to their harmonic positions
- **CC Status Bar**: Real-time display of control values
- **2D and 3D Modes**: Choose PyGame (2D) or ModernGL (3D with bloom)

## Chromatic Harmonic Mapping

The Optimized Chromatic prototypes prioritize simple ratios for consistent musical intervals:

| Key | Harmonic (n) | Ratio | Interval | Cents |
|-----|--------------|-------|----------|-------|
| C   | 1  | 1/1   | Fundamental | 0 |
| C#  | 17 | 17/16 | Minor Second | 105 |
| D   | 9  | 9/8   | Major Second | 204 |
| Eb  | 19 | 19/16 | Harmonic m3 | 298 |
| E   | 5  | 5/4   | Major Third | 386 |
| F   | 21 | 21/16 | Perfect 4th | 471 |
| F#  | 11 | 11/8  | Tritone | 551 |
| G   | 3  | 3/2   | Perfect Fifth | 702 |
| Ab  | 13 | 13/8  | Harmonic m6 | 840 |
| A   | 27 | 27/16 | Major Sixth | 906 |
| Bb  | 7  | 7/4   | Harmonic Seventh | 969 |
| B   | 15 | 15/8  | Major Seventh | 1088 |

These prototypes are automatically transposed to match the octave you're playing.

## Operating Modes

### Keyboard Mode

Maps chromatic keys to harmonic prototypes. Each semitone uses a specific harmonic ratio, transposed to match your playing octave.

**Stacking Mode** (toggle with CC22):
- **OFF**: Single voice per key (default)
- **ON**: Plays BOTH transposed (pitch-correct) AND natural (spectral) frequencies
- **Mix Control** (CC67): Balance between transposed (127) and natural (0)

### Pad Mode

Direct mapping for 8×8 pad controllers (Novation Launchpad):
- Bottom-left pad = Harmonic 1
- Top-right pad = Harmonic 64
- LED feedback shows active harmonics
- **Split Mode** (toggle with CC104):
  - Lower 4 rows: Momentary (release to stop)
  - Upper 4 rows: Toggle/latch (press to start, press again to stop)

**Toggle**: Press Note 8 to switch between Keyboard and Pad modes

## Hardware Setup

### Required
- MIDI keyboard or pad controller
- Computer running Linux, macOS, or Windows

### Supported Controllers
- **Primary**: Arturia KeyLab 61 MkII, generic MIDI keyboard
- **Pad Mode**: Novation Launchpad Mini (other 8×8 grids may work)
- **Modulation** (optional): Arturia Minilab3 or any secondary MIDI controller

### Surge XT Configuration

1. Download [Surge XT](https://surge-synthesizer.github.io/) (free, open-source)
2. Enable OSC in Surge XT settings:
   - Go to Menu → OSC Settings
   - Enable "OSC In"
   - Set port to **53280** (default in config)
3. Create a patch with long sustain/release for smooth harmonic tones

## MIDI CC Mapping

| CC | Function | Range |
|----|----------|-------|
| 22 | Stacking Mode Toggle | 0-63=OFF, 64-127=ON |
| 67 | Stacking Mix | 0=Natural only, 127=Transposed only |
| 74 | f₁ (Base Frequency) | 0=32.5Hz, 127=65Hz |
| 104 | Split Mode Toggle (Pad Mode) | >0 = toggle |
| 111 | Panic (Kill All Notes) | >0 = trigger |

| Note | Function |
|------|----------|
| 8 | Toggle Keyboard/Pad Mode |
| 111 | Panic (Kill All Notes) |

## Command Line Usage

### Harmonic Beacon

```bash
# Basic usage (auto-detects MIDI)
python -m harmonic_beacon.main

# With visualizer broadcast
python -m harmonic_beacon.main --broadcast

# Mock mode (no Surge XT required)
python -m harmonic_beacon.main --mock

# Enable MPE output
python -m harmonic_beacon.main --mpe

# Custom f₁ starting value
python -m harmonic_beacon.main --f1 50.0

# Disable modulation controller
python -m harmonic_beacon.main --no-modulation

# List available MIDI ports
python -m harmonic_beacon.main --list-ports

# Enable MIDI debug logging
python -m harmonic_beacon.main --midi-debug

# Quiet mode (minimal output)
python -m harmonic_beacon.main --quiet
```

### Harmonic Visualizer

```bash
# 2D mode (PyGame, default)
python -m harmonic_visualizer.main

# 3D mode (ModernGL with bloom)
python -m harmonic_visualizer.main --3d

# Custom OSC port
python -m harmonic_visualizer.main --port 9001

# Disable energy lines
python -m harmonic_visualizer.main --no-lines
```

**Keyboard shortcuts in visualizer:**
- `E` — Toggle energy lines (particles)
- `H` — Toggle HUD
- `F` — Toggle fullscreen
- `ESC` — Quit

## Configuration

Edit `harmonic_beacon/config.py` to customize:

- **f₁ range**: `F1_MIN`, `F1_MAX`, `DEFAULT_F1`
- **Anchor note**: `ANCHOR_MIDI_NOTE` (which note represents f₁)
- **Chromatic prototypes**: `CHROMATIC_PROTOTYPES` array
- **Pad Mode defaults**: `PAD_MODE_ENABLED_BY_DEFAULT`, `SPLIT_MODE_ENABLED_BY_DEFAULT`
- **OSC ports**: `OSC_PORT` (Surge XT), `BROADCAST_PORT` (visualizer)
- **Hardware mappings**: `PAD_ANCHOR_NOTE`, `PAD_MODE_TOGGLE_NOTE`, etc.

## Architecture

```
MIDI Controller → Harmonic Beacon → Surge XT (sound)
                        ↓
                  Visualizer (display)
```

1. **MIDI Input**: Beacon receives Note-On/Off and CC messages
2. **Harmonic Calculation**: Maps keys to natural harmonic frequencies using KeyMapper
3. **OSC Output**: Sends frequency-based notes to Surge XT
4. **Broadcast**: Optionally sends state updates to visualizer via OSC

## How Stacking Mode Works

When Stacking Mode is ON (CC22 ≥ 64):

1. **Primary Voice (Transposed)**: Harmonic prototype shifted to match 12TET pitch
   - Ensures notes are "in tune" with standard instruments
   - Gain controlled by Mix (CC67)

2. **Secondary Voice (Natural)**: Original harmonic at its spectral position
   - Pure harmonic ratio sound
   - Gain controlled by inverse Mix

Example: Press E (prototype n=5):
- Transposed: 5/4 ratio transposed to E's octave (pitch-correct)
- Natural: Raw n=5 frequency (pure harmonic timbre)
- Mix at 64 (center): Both play at equal volume

## Troubleshooting

### Permission denied: /dev/snd/seq

Your user needs access to ALSA MIDI:

```bash
sudo usermod -a -G audio $USER
```

Log out and back in for changes to take effect.

### No MIDI ports found

1. Check controller is connected: `python -m harmonic_beacon.main --list-ports`
2. On Linux, verify ALSA/JACK is configured
3. For filtered device matching, set `MIDI_PORT_PATTERN` in `harmonic_beacon/config.py`

### Surge XT not receiving notes

1. Verify OSC is enabled in Surge XT settings
2. Check port matches (default: 53280)
3. Test with `--mock` mode to see if Beacon is working
4. Check firewall isn't blocking localhost UDP

### Visualizer shows black screen

1. Ensure Beacon is running with `--broadcast` flag
2. Check visualizer port matches `BROADCAST_PORT` (default: 9001)
3. Try keyboard mode first (Pad Mode has different layout assumptions)

## Dependencies

- **mido** (≥1.3.0) — MIDI message handling
- **python-rtmidi** (≥1.5.0) — Real-time MIDI I/O
- **python-osc** (≥1.8.3) — OSC communication
- **pygame** (≥2.5.0) — 2D visualizer (required)
- **moderngl** (≥5.8.0) — 3D visualizer (optional)
- **numpy** (≥1.24.0) — Visualizer math (optional)

## Literate Program

The Harmonic Beacon core is documented as a **literate program** — a single
document that is both human-readable narrative and machine-extractable source
code. The file `harmonic-beacon.lit.md` weaves prose, diagrams, and code in
"psychological order" (the order that best explains the system, not the order
the compiler demands).

### What's in it

The literate program covers all 10 modules of `harmonic_beacon/`:

| Section | Module | What it explains |
|---------|--------|-----------------|
| The Mathematics | `harmonics.py` | The harmonic series equation, cents, frequency mapping |
| Configuration | `config.py` | Chromatic prototypes, CC assignments, OSC networking |
| Key Mapping | `key_mapper.py` | How MIDI keys become harmonic numbers |
| MIDI Events | `midi_handler.py` | Receiving input from physical controllers |
| Voice Management | `polyphony.py` | Tracking active notes and voice allocation |
| Harmonic Chorus | `lfo.py` | Triangle-wave sweep between harmonics |
| OSC Output | `osc_sender.py` | Sending exact frequencies to Surge XT |
| MPE Output | `mpe_sender.py` | MIDI Polyphonic Expression for microtonal control |
| The Orchestrator | `main.py` | The real-time event loop tying everything together |

### Reading the document

Open `harmonic-beacon.lit.md` in any Markdown viewer (VS Code, Obsidian, GitHub)
or generate a PDF:

```bash
# Install pandoc + xelatex (one-time)
sudo apt install pandoc texlive-xetex

# Generate PDF
pandoc harmonic-beacon.lit.md -o harmonic-beacon.pdf \
  --pdf-engine=xelatex --toc --number-sections \
  -V geometry:margin=1.5cm
```

A pre-built PDF is included at `harmonic-beacon.pdf`.

### Extracting source code from the document

The `.lit.md` is the **single source of truth**. You can regenerate the
Python source files from it:

```bash
# Install tsx (one-time)
npm install -g tsx

# Extract source files
npx tsx ~/.hermes/skills/creative/literate-programming/scripts/tangle.ts \
  harmonic-beacon.lit.md --output-dir .

# Verify extraction matches current source
npx tsx ~/.hermes/skills/creative/literate-programming/scripts/tangle.ts \
  harmonic-beacon.lit.md --output-dir . --verify
```

### Philosophy

This literate program is a probe for **Harmonic Information Theory (HIT)**.
While the code makes the Beacon *work*, the narrative makes it *understood*.
Every code block is preceded by prose explaining *why* it exists, not just
*what* it does. The document is meant to be read cover-to-cover by someone
who wants to understand the system deeply — from the physics of the harmonic
series to the real-time event loop that makes it audible.

## License

MIT License — See LICENSE file for details.

## Contributing

Issues and pull requests welcome! Please ensure:
- Tests pass: `pytest tests/`
- Code follows existing style
- Documentation is updated for new features

## Acknowledgments

Inspired by the mathematical beauty of the natural harmonic series and the pioneering work in just intonation, spectral music, and microtonal composition.

Built with Python, Surge XT, and open-source tools.
