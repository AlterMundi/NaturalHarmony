# Source of Truth - Architectural Decisions
## Date: 2026-02-11

## Principle
**Current code behavior is the source of truth unless explicitly changed.**

All documentation, tests, and comments must be updated to match the actual implementation.

## Confirmed Current Behavior (Lock These)

### 1. Architecture
- **Single-voice-per-layer** system with optional Stacking Mode
- Stacking Mode (CC22) allows playing both transposed (pitch-correct) AND natural (spectral) frequencies
- NOT a "dual-voice always on" system (this was historical)

### 2. Dependencies
- **python-osc** (NOT pyliblo or pyliblo3)
- mido + python-rtmidi for MIDI
- pygame for 2D visualizer
- moderngl for 3D visualizer (optional)

### 3. Key Mapping
- Uses **Chromatic Prototypes** (CHROMATIC_PROTOTYPES in config.py)
- KeyMapper transposes prototypes to match played octave
- Local harmonic matching is **disabled** (see key_mapper.py:146)
- Prototypes: [1, 17, 9, 19, 5, 21, 11, 3, 13, 27, 7, 15]

### 4. Defaults
- `DEFAULT_F1 = 65.0` Hz (between C2 and C#2)
- `F1_MIN = 32.5` Hz, `F1_MAX = 65.0` Hz
- Pad Mode enabled by default: `PAD_MODE_ENABLED_BY_DEFAULT = True`
- Stacking Mode disabled by default (user toggles via CC22)
- Split Mode disabled by default (user toggles via CC104)
- `DEFAULT_STACKING_MIX = 64` (balanced mix)

### 5. Operating Modes
- **Keyboard Mode**: Chromatic mapping with optional stacking
- **Pad Mode**: Direct 1:1 mapping of pads to harmonics 1-64
- **Split Mode** (Pad Mode only): Lower 4 rows momentary, upper 4 rows toggle

### 6. OSC Protocol
- Surge XT target: port 53280 (not 9000)
- Visualizer broadcast: port 9001
- Message format: `/fnote` with frequency (not MIDI note)
- Pitch expression: `/ne/pitch` for real-time f₁ modulation

### 7. Hardware Support
- Primary: Arturia KeyLab 61 MkII
- Pad controller: Novation Launchpad Mini (stride-16 layout)
- Modulation controller: Arturia Minilab3 (optional, secondary MIDI port)

## Decisions on Legacy/Ambiguous Items

### Remove from Docs
- ❌ "Beacon Voice" + "Playable Voice" dual-voice concept
- ❌ References to "pyliblo" or "pyliblo3"
- ❌ References to "octave borrower" module (doesn't exist)
- ❌ Claims of always playing two voices simultaneously

### Keep (But Document Properly)
- ✅ Stacking Mode (modern replacement for dual-voice concept)
- ✅ Effective harmonic numbers (can be float after transposition)
- ✅ Modulation controller behavior (re-tunes anchor on note press)
- ✅ LFO chorus system (sweeps between multiple matching harmonics)

### Add Missing Documentation
- ✅ Split Mode for Launchpad
- ✅ Stacking Mix control (CC67)
- ✅ Panic button (Note 111)
- ✅ Mode toggle (Note 8 for Pad/Keyboard switch)
- ✅ Complete CC mapping table
- ✅ Visualizer architecture and OSC protocol

## License Decision
**Action Required**: Choose one:
1. Add MIT LICENSE file to match README claim
2. Remove license claim from README
3. Change to different license

**Recommendation**: Add MIT LICENSE file (most permissive, matches README)

## .gitignore Decision
**Action Required**: Choose one:
1. Remove TASKS.md from git tracking (follow .gitignore)
2. Remove TASKS.md from .gitignore (keep tracking it)

**Recommendation**: Remove from .gitignore (it's useful to track project status)

## Test Suite Strategy
- Remove/rewrite tests for removed APIs
- Add tests for current KeyMapper behavior
- Add tests for Stacking Mode logic
- Keep tests deterministic (no hardware dependencies)
- Mock all OSC/MIDI I/O

## Documentation Update Strategy
- README: Complete rewrite as operator guide
- SPEC: Update to v2.0 reflecting current architecture
- TASKS: Refresh backlog to match current state
- New: ARCHITECTURE.md (deep technical dive)
- New: CONTROLLERS.md (hardware mappings)
