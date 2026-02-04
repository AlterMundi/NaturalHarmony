# The Harmonic Beacon – Development Status

## Completed Milestones

### Core Engine
- [x] **Harmonic Calculations**: Exact frequency mapping ($f_n = n \times f_1$).
- [x] **MIDI Handling**: Input processing with `mido` and `rtmidi`.
- [x] **Polyphony**: Robust voice tracking and allocation.
- [x] **Modulation**: Smooth real-time $f_1$ shifting via MIDI CC.

### Modes
- [x] **Keyboard Mode**: 12-semitone mapping based on intervals.
- [x] **Pad Mode**: Direct mapping of Harmonics 1-64 on an 8x8 Grid.
- [x] **Panic Button**: Emergency voice kill via CC 111 / Note 111.

### Hardware Integration
- [x] **Arturia KeyLab 61 MkII**: Full support for keys and sliders.
- [x] **Novation Launchpad Mini**: Pad Mode with LED feedback (Green).
- [x] **Akai Force**: (Partial/tested) - Replaced by Launchpad for Pad Mode.

### Visualization
- [x] **Harmonic Visualizer**: Real-time 3D OpenGL application.
- [x] **Grid View**: Shows active pads/harmonics with frequencies.
- [x] **OSC Broadcast**: Beacon broadcasts state to Visualizer.

## Future / Pending
- [ ] Record MIDI output to file.
- [ ] Save/Load presets for $f_1$ and mappings.
- [ ] Advanced LFO shapes.
