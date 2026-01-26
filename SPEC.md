# Project: The Harmonic Beacon
## Technical Specification v1.1

### Core Concept
A Python-based MIDI middleware that maps a standard 12-key controller to the Natural Harmonic Series. It creates a "Harmonic Beacon" effect by triggering both a transposed "playable" note and the raw integer harmonic simultaneously.

### Technical Environment
- **Host:** Debian Linux
- **Framework:** Python (mido, python-rtmidi, pyliblo/OSC)
- **Synth Target:** Surge XT (via OSC for high-frequency precision)
- **Primary Controller:** Arturia KeyLab 61 MkII

### Mathematical Logic
- **Base Frequency ($f_1$):** Default 54.0 Hz.
- **Harmonic Series:** $f_n = n \times f_1$
- **Dual-Voice Output:**
    1. **Beacon Voice:** Raw Harmonic ($f \times n$).
    2. **Playable Voice:** Harmonic reduced to the playing octave using $f \times (n/2^x)$.
- **Dynamic Modulation:** KeyLab Slider/Knob must update $f_1$ in real-time, shifting all active frequencies.

### Harmonic Mapping (12-Key Octave)
| MIDI Key (Relative) | Harmonic ($n$) | Ratio ($n/2^x$) | Interval |
| :--- | :--- | :--- | :--- |
| C (0) | 1 | 1/1 | Fundamental |
| C# (1) | 17 | 17/16 | Minor Second |
| D (2) | 9 | 9/8 | Major Second |
| Eb (3) | 19 | 19/16 | Harmonic m3 |
| E (4) | 5 | 5/4 | Major Third |
| F (5) | 21 | 21/16 | Narrow Fourth |
| F# (6) | 11 | 11/8 | Mystic Tritone |
| G (7) | 3 | 3/2 | Perfect Fifth |
| Ab (8) | 13 | 13/8 | Harmonic m6 |
| A (9) | 27 | 27/16 | Major Sixth |
| Bb (10) | 7 | 7/4 | Harmonic Seventh |
| B (11) | 15 | 15/8 | Major Seventh |

### Implementation Notes
- Use `pyliblo` to send OSC messages to Surge XT.
- Ensure polyphony is handled by tracking MIDI Note-On/Note-Off IDs.
- The $f_1$ shift must be smooth (interpolated) to avoid digital clicks in the synth.