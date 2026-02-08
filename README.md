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
- **python-osc** — OSC communication with Surge XT

## Troubleshooting

### Permission denied: /dev/snd/seq

If you see an error like `ALSA lib seq_hw.c:466:(snd_seq_hw_open) open /dev/snd/seq failed: Permission denied`, your user does not have permission to access the ALSA sequencer.

To fix this, add your user to the `audio` group:

```bash
sudo usermod -a -G audio $USER
```

Then **log out and log back in** (or reboot) for the changes to take effect.

## License

MIT License — See LICENSE file for details.

## Acknowledgments

Based on the mathematical beauty of the natural harmonic series and the pioneering work in just intonation and spectral music.
