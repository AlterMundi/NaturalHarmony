# ARCHIVE — NaturalHarmony

## Status: ARCHIVED (2026-07-18)

This repository is **retired from active development**. Its living ideas have
been carried into the re-architected beacon ecosystem. Nothing here should
receive new features. The repo is archived as-is and remains **readable
history**: git history preserves everything, including the code that was
ported or superseded.

## What the system was

MIDI middleware and visualizer for playing the **natural harmonic series**:
it transformed standard MIDI keyboards and Launchpad-style pad controllers
into microtonal instruments tuned to natural harmonics (not equal
temperament). Components:

- `harmonic_beacon/` — MIDI→OSC engine mapping notes to harmonic frequencies
  (Optimized Chromatic mapping, keyboard and pad modes).
- `harmonic_exciter/` — MIDI→ESP32 bridge that drove the physical tines
  beacon (hardware no longer exists; see the `harmonic-beacon-tines` archive).
- `harmonic_visualizer/` — real-time 2D/3D visualization of active harmonics
  via OSC.
- `harmonic_shaper/` — the original software Shaper, which was forked and
  evolved in `digital-beacon` and is now canonical at `harmonic-shaper`.

## Destination map (where each subsystem lives now)

**→ `harmonic-shaper`:**

- harmonic mapping (`harmonic_beacon/harmonics.py`,
  `harmonic_beacon/key_mapper.py`) — ported dependency-free into
  `harmonic-shaper/src/harmonic_shaper/harmonic_mapping.py` (task T2.3).
- the Shaper lineage (`harmonic_shaper/`) — evolved through the
  `digital-beacon` fork (32 voices + waveshaper + LFO + sidechain); the
  canonical successor is the standalone **`harmonic-shaper`** repo
  (`pip install -e .`, `contracts/shaper.contract.json`).

**Superseded concepts:**

- Launchpad control (`harmonic_exciter/launchpad_control.py`) and the
  visualizer concepts (`harmonic_visualizer/`) — superseded by
  **`harmonic-weaver`** routing and future F5 work in the new ecosystem.
- `harmonic_exciter/` as a whole — tied to the retired physical tines
  hardware; preserved here as history only.

## Successors

- **`harmonic-shaper`** — canonical harmonic mapping + synth.
- **`beacon-spatial`** — spatialized nature layer (grew out of the
  `digital-beacon` fork's other half).
- **`harmonic-weaver`** — routing/modulation and future control/visual
  concepts.

For orientation inside this archive, `README.md`, `MEMORY.md`,
`harmonic-beacon.lit.md` (the literate program, with PDF), and `docs/` remain
in place. Do not resurrect modules from here without checking the successor
repos first.
