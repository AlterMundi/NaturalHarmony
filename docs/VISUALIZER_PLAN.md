# Harmonic Visualizer
## Implementation Reference (Current)

This document describes the current visualizer behavior and integration points.

## 1. Role in the System
The visualizer is a passive OSC consumer.

- It does not generate sound.
- It does not compute synthesis frequencies.
- It renders state broadcast by `harmonic_beacon`.

## 2. Process Topology

```text
MIDI Controller -> Harmonic Beacon -> Surge XT
                      |
                      +-> OSC Broadcast (/beacon/*) -> Harmonic Visualizer
```

Default broadcast port: `9001`.

## 3. Runtime Entry Points

- Visualizer launcher: `python -m harmonic_visualizer.main`
- 2D mode: default (`renderer.py`)
- 3D mode: `--3d` (`renderer_3d.py`)

CLI flags:
- `--port <int>`
- `--no-lines`
- `--3d`

## 4. OSC Protocol Consumed

The visualizer listens for:
- `/beacon/f1`
- `/beacon/anchor`
- `/beacon/voice/on` with args:
  - `voice_id`, `freq`, `gain`, `source_note`, `harmonic_n`
- `/beacon/voice/off`
- `/beacon/voice/freq`
- `/beacon/key/on`
- `/beacon/key/off`
- `/beacon/cc`
- `/beacon/mode/pad`

Backward compatibility:
- `/beacon/voice/on` 4-arg payload is tolerated by receiver fallback.

## 5. Shared State Model
`VisualizerState` tracks:
- global tuning state (`f1`, `anchor_note`)
- active and fading voices
- pressed keys
- CC values
- current pad-mode flag

Rendering reads this state each frame.

## 6. Rendering Behavior

### 6.1 2D Renderer (`renderer.py`)
- Harmonic spine display
- Keyboard display
- CC status bar
- Optional energy lines

### 6.2 3D Renderer (`renderer_3d.py`)
- Frequency ruler and keyboard/pad view
- Particle/line effects
- Optional HUD
- Fullscreen toggle support

Interactive keys (both modes where available):
- `E` toggle energy lines/particles
- `H` toggle HUD
- `F` toggle fullscreen (3D)
- `ESC` quit

## 7. Operational Notes
- Start beacon with `--broadcast` to feed visualizer.
- If no `/beacon/*` messages arrive, UI will show idle baseline state.
- Hardware/MIDI troubleshooting belongs to beacon documentation.

## 8. Verification Checklist
1. Run beacon with `--broadcast`.
2. Run visualizer (`--3d` optional).
3. Press/release notes and verify key + voice updates.
4. Change CC values and verify state changes.
5. Toggle pad mode and verify visual mode updates.
