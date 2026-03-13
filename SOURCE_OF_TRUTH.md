# Source of Truth - Architectural Decisions
## Date: 2026-02-11

## Principle
Current runtime behavior in `harmonic_beacon` and `harmonic_visualizer` is authoritative.
Documentation and tests must describe that behavior, not historical drafts.

## Locked Behavioral Truths

### Architecture
- System is not permanently dual-voice.
- Stacking mode (CC22) enables layered transposed + natural playback.
- Keyboard mode and pad mode are runtime toggles.

### Dependencies
- Runtime OSC stack: `python-osc`.
- MIDI stack: `mido` + `python-rtmidi`.
- Visualizer: `pygame`; 3D mode adds `moderngl` + `numpy`.

### Key Mapping
- Uses `CHROMATIC_PROTOTYPES` from `harmonic_beacon/config.py`.
- KeyMapper transposes prototypes by octave toward played-key targets.
- Local nearest-harmonic branch remains intentionally disabled.

### Defaults
- `DEFAULT_F1 = 65.0`
- `PAD_MODE_ENABLED_BY_DEFAULT = True`
- `SPLIT_MODE_ENABLED_BY_DEFAULT = False`
- `OSC_PORT = 53280`
- `BROADCAST_PORT = 9001`

### OSC Broadcast Schema
Current visualizer payload contract:
- `/beacon/f1`
- `/beacon/anchor`
- `/beacon/voice/on` (voice_id, freq, gain, source_note, harmonic_n)
- `/beacon/voice/off`
- `/beacon/voice/freq`
- `/beacon/key/on`
- `/beacon/key/off`
- `/beacon/cc`
- `/beacon/mode/pad`

## Repository Policy Decisions (Resolved)
- License: MIT file added at repo root (`LICENSE`).
- Test discovery: `pytest.ini` restricts discovery to `tests/`.
- Tracked planning docs: `.gitignore` no longer excludes `TASKS.md`.

## Deprecated Concepts (for docs cleanup)
- "pyliblo/pyliblo3 runtime dependency"
- "always dual-voice output"
- legacy octave-borrower references
