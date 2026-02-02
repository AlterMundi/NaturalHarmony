# Harmonic Beacon Visualizer

Real-time visualization of harmonic series, keyboard state, and frequency output.

---

## Architecture

```
┌─────────────────┐
│   MIDI Input    │ ─────────────────────────────────────────┐
│  (KeyLab MKII)  │                                          │
└────────┬────────┘                                          │
         │                                                   │
         ▼                                                   ▼
┌─────────────────┐      OSC broadcast          ┌─────────────────────┐
│ Harmonic Beacon │ ───────────────────────────▶│     Visualizer      │
│   (main.py)     │   /beacon/voice/*           │                     │
└────────┬────────┘   /beacon/f1                │ - Passive observer  │
         │            /beacon/cc/*              │ - No calculations   │
         ▼                                      │ - Pure reflection   │
┌─────────────────┐                             └─────────────────────┘
│    Surge XT     │
└─────────────────┘
```

**Key principle**: Visualizer never calculates frequencies or LFO values. It only renders what it receives via OSC. LFO effects are visible because OSC broadcasts the *current* frequency, which changes as LFO sweeps.

---

## OSC Broadcast Protocol

Harmonic Beacon broadcasts to `localhost:9001` (configurable):

| Address | Arguments | Description |
|---------|-----------|-------------|
| `/beacon/f1` | `f` (Hz) | Current f₁ value |
| `/beacon/anchor` | `i` (MIDI note) | Anchor note |
| `/beacon/voice/on` | `i` voice_id, `f` freq, `f` gain | Voice activated |
| `/beacon/voice/off` | `i` voice_id | Voice released |
| `/beacon/voice/freq` | `i` voice_id, `f` freq | Frequency update (LFO sweep) |
| `/beacon/key/on` | `i` note, `i` velocity | Key pressed |
| `/beacon/key/off` | `i` note | Key released |
| `/beacon/cc` | `i` cc_num, `i` value | CC change |

---

## Layout

```
┌───────────────────────────────────────────────────────────────────┐
│                                                                   │
│   ┌─────────────────────────────┐ ┌─────────────────────────────┐ │
│   │                             │ │                             │ │
│   │     HARMONIC SPINE          │ │     KEYBOARD / VOICES       │ │
│   │                             │ │                             │ │
│   │   n=16 ○                    │ │   [pressed keys shown]      │ │
│   │   n=15 ○                    │ │   [energy lines to spine]   │ │
│   │   n=14 ○                    │ │                             │ │
│   │   ...                       │ │   61 keys + virtual range   │ │
│   │   n=3  ●━━━━━━━━━━━━━━━━━━━━│━│━━━(energy line)━━━━━━━━━━━━│ │
│   │   n=2  ○                    │ │                             │ │
│   │   n=1  ◉ ← f₁ = 32.7 Hz     │ │                             │ │
│   │                             │ │                             │ │
│   └─────────────────────────────┘ └─────────────────────────────┘ │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│  CC STATUS BAR                                                    │
│  [Tolerance: ▓▓▓▓░░░░ 25¢] [LFO: 1.0Hz] [Mode: Key Anchor] [AT:●] │
└───────────────────────────────────────────────────────────────────┘
```

---

## Proposed Changes

### Harmonic Beacon (modify)

#### [MODIFY] [osc_sender.py](file:///home/nicolas/OS_projects/NaturalHarmony/harmonic_beacon/osc_sender.py)

Add broadcast methods for visualizer:
- `broadcast_f1(hz)` 
- `broadcast_voice_on(voice_id, freq, gain)`
- `broadcast_voice_freq(voice_id, freq)` — called on LFO updates
- `broadcast_key_on/off(note, velocity)`
- `broadcast_cc(cc_num, value)`

#### [MODIFY] [main.py](file:///home/nicolas/OS_projects/NaturalHarmony/harmonic_beacon/main.py)

Insert broadcast calls at:
- `_handle_note_on/off` → broadcast key + voice events
- `_update_lfo_chorus` → broadcast frequency updates
- CC handlers → broadcast CC changes

---

### Visualizer (new package)

#### [NEW] `harmonic_visualizer/` package

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `config.py` | OSC port, colors, layout settings |
| `osc_receiver.py` | Listens to `/beacon/*` messages |
| `state.py` | Holds current keyboard/voice/CC state |
| `renderer.py` | PyGame/ModernGL rendering |
| `spine.py` | Harmonic spine widget (vertebrae design) |
| `keyboard.py` | Keyboard widget with 61+ keys |
| `energy_lines.py` | Optional bezier lines from keys to spine |
| `cc_bar.py` | Bottom CC status bar |
| `main.py` | Entry point |

---

## Keyboard Range

- **Physical**: 61 keys (A0–C6 or configurable)
- **Virtual**: ±3 octaves via transpose (full MIDI range 0–127 accessible)
- **Display**: Show physical window highlighted within full range
- Configurable via `config.py` for different keyboard sizes

---

## Rendering Approach

**Phase 1**: PyGame (2D, fast iteration)
- Immediate mode rendering
- Simple shapes for vertebrae
- Bezier curves for energy lines

**Phase 2** (future): ModernGL
- Shader-based glow effects
- 3D spine geometry
- VR-ready data structures

---

## Verification Plan

### Manual Testing
1. Run Harmonic Beacon with `--broadcast` flag
2. Run visualizer in separate terminal
3. Press keys → verify spine nodes light up
4. Enable LFO → verify frequency sweep visible in spine animation
5. Adjust CC sliders → verify status bar updates
6. Toggle energy lines → verify connections appear

### Automated Tests
- Unit tests for OSC receiver message parsing
- State management tests
