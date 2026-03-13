# Natural Harmony
## Technical Specification v2.0 (Current Implementation)

## 1. System Overview
Natural Harmony is a Python MIDI middleware and visualization system built around the natural harmonic series.

It consists of:
- `harmonic_beacon`: runtime MIDI/OSC/MPE engine.
- `harmonic_visualizer`: passive OSC visualizer (2D PyGame or 3D ModernGL).

## 2. Runtime Components

### 2.1 Harmonic Beacon
Main entry point: `python -m harmonic_beacon.main`

Responsibilities:
- Receive MIDI note/CC events.
- Map key presses to harmonic-derived frequencies.
- Send frequency notes to Surge XT over OSC (`/fnote`, `/fnote/rel`, `/ne/pitch`).
- Optionally send MPE output on virtual MIDI port.
- Optionally broadcast state to the visualizer via OSC.

### 2.2 Harmonic Visualizer
Main entry point: `python -m harmonic_visualizer.main`

Responsibilities:
- Receive `/beacon/*` OSC broadcast messages.
- Maintain visualization state (voices, keys, CC, mode).
- Render 2D or 3D UI; no synthesis and no MIDI output.

## 3. Defaults and Configuration
Source: `harmonic_beacon/config.py`

Key defaults:
- `DEFAULT_F1 = 65.0`
- `F1_MIN = 32.5`
- `F1_MAX = 65.0`
- `PAD_MODE_ENABLED_BY_DEFAULT = True`
- `SPLIT_MODE_ENABLED_BY_DEFAULT = False`
- `OSC_PORT = 53280` (Surge XT)
- `BROADCAST_PORT = 9001` (visualizer)

## 4. Musical Mapping Model

### 4.1 Keyboard Mode (Optimized Chromatic)
Each pitch class maps to a prototype harmonic from `CHROMATIC_PROTOTYPES`:
`[1, 17, 9, 19, 5, 21, 11, 3, 13, 27, 7, 15]`

The prototype frequency is octave-transposed toward the played key's 12TET target.

Important behavior:
- Local nearest-harmonic matching logic is intentionally disabled.
- The engine prioritizes stable/simple prototype relationships.

### 4.2 Pad Mode
- Direct mapping from 8x8 grid to harmonics `1..64`.
- Launchpad layout support with bottom-left as `n=1`.

### 4.3 Split Mode (Pad Mode)
- Toggle via `CC104`.
- Lower half: momentary triggers.
- Upper half: latching toggles.

### 4.4 Stacking Mode
- Toggle via `CC22`.
- OFF: single primary/transposed voice.
- ON: layered transposed + natural voices.
- Mix via `CC67` (`0 = natural-heavy`, `127 = transposed-heavy`).

## 5. Performance and Control

### 5.1 f1 Modulation
- Controlled by `CC74`.
- Smoothed by interpolation (`F1_SMOOTHING_RATE`).
- Active voices are pitch-shifted in real time.

### 5.2 Panic
- Triggered by note/control value `111`.
- Forces all notes off and clears tracked state.

### 5.3 Secondary Modulation Controller
- Optional second MIDI input (`SECONDARY_MIDI_PORT_PATTERN`).
- Incoming notes can retune anchor/f1 mapping without direct audio triggering.

## 6. Protocols

### 6.1 OSC to Surge XT
Primary messages:
- `/fnote [frequency, velocity, note_id]`
- `/fnote/rel [frequency, release_velocity, note_id]`
- `/allnotesoff []`
- `/ne/pitch [note_id, semitone_offset]`

### 6.2 OSC Broadcast to Visualizer
- `/beacon/f1`
- `/beacon/anchor`
- `/beacon/voice/on` (voice_id, freq, gain, source_note, harmonic_n)
- `/beacon/voice/off`
- `/beacon/voice/freq`
- `/beacon/key/on`
- `/beacon/key/off`
- `/beacon/cc`
- `/beacon/mode/pad`

## 7. CLI Surface

### 7.1 Beacon CLI options
- `--mock`, `--quiet`, `--list-ports`, `--f1`
- `--broadcast`
- `--mpe`, `--mock-mpe`
- `--modulation-port`, `--no-modulation`
- `--midi-debug`

### 7.2 Visualizer CLI options
- `--port`
- `--no-lines`
- `--3d`

## 8. Dependencies
From `requirements.txt`:
- `mido`
- `python-rtmidi`
- `python-osc`
- `pygame`
- `moderngl`
- `numpy`

## 9. Non-Goals / Historical Notes
- No `pyliblo` runtime dependency.
- No permanent “dual-voice always on” model.
- Legacy design notes are superseded by this specification.
