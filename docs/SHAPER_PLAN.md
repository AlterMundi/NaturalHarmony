# Epic: Cymatic Harmonic Shaper
## NaturalHarmony — Next Iteration Plan

---

## Context & Experiment Goal

We have a physical setup:
- **Two speakers** connected to a sound card feed sound into a **sealed tube**
- The tube is capped by a **tensed balloon** with a **small mirror** glued to its face
- A **laser** points at the mirror; the reflected dot draws patterns on the wall
- The pattern shape encodes the **interference pattern** between active harmonics

We currently use the **Launchpad Mini in latch mode** to hold up to 5 harmonics from the natural series.
We need **fine per-harmonic control** of: **gain**, **stereo pan**, **phase**, and future parameters.

The **Minilab3** is our hardware shaper controller (already partially wired in the system as `SECONDARY_MIDI_PORT_PATTERN = "Minilab"`).

---

## Core Design Decision: Where Does the Shaper Live?

### Option A — Sidechain shaper (intercepts Beacon→Surge XT OSC)
- New `harmonic_shaper` process sits between Beacon and Surge XT
- Listens to `/beacon/*` broadcasts, injects per-harmonic gain/pan into Surge XT OSC
- **Problem:** Surge XT doesn't have per-voice real-time gain/pan via OSC in a clean way;
  we can't easily shape phase at all.

### Option B — Direct Audio Synthesis (Python + sounddevice)
- `harmonic_shaper` synthesizes pure sine waves at harmonic frequencies
- Per-harmonic independent gain, stereo pan, phase
- Outputs directly to sound card via `sounddevice` (bypassing Surge XT for the shaper voices)
- Beacon still drives Surge XT for the full harmonic experience; shaper handles the "experiment channel"
- **Recommended for the cymatic experiment**, where we need exact phase control

### Option C — Integrated into Beacon
- Extend Beacon's voice engine with per-harmonic parameter store
- Minilab3 controls shaper params via existing secondary MIDI handler
- Outputs shaped voices via existing OSC layer + new direct audio path
- Cleanest long-term, highest refactor cost

**Recommended starting point: Option B (standalone shaper)** — makes the experiment self-contained
and doesn't risk breaking the existing Beacon. Can be integrated later.

---

## Proposed System Architecture

```
Launchpad Mini
    │ (MIDI latch pads)
    ▼
harmonic_beacon ──── /fnote OSC ──── Surge XT ──── Audio Out (full mix)
    │
    │ /beacon/voice/on,off,freq (OSC broadcast)
    ▼
harmonic_shaper  ◄── Minilab3 MIDI (knobs/faders)
    │            ◄── HTTP/WS API (UI + automation)
    │            ◄── OSC API (experiment scripts)
    │
    ├── Voice Parameter Store (per harmonic_n: gain, pan, phase, ...)
    │
    ├── Audio Synthesis Engine (sounddevice, pure sines)
    │   └── Real-time mixing with gain/pan/phase applied
    │
    ├── Web Control UI (served locally, synced via WebSocket)
    │
    ├── Experiment Runner (scripts that evolve params over time)
    │
    └── Dataset Logger (timestamped parameter states → CSV/JSON)
```

---

## Epic Cards (Lattice Tasks)

### EPIC-0: Harmonic Shaper Epic (parent spike)
> Umbrella card. All other cards are subtasks.

### Card 1: `harmonic_shaper` Core Engine
- New Python package `harmonic_shaper/`
- Listens to `/beacon/voice/on|off|freq` OSC broadcasts
- Maintains `VoiceParameterStore`: dict by `harmonic_n` → {gain, pan, phase}
- Real-time audio synthesis via `sounddevice` (or `pyaudio`)
- Applies parameters per-sine on each buffer callback
- Config: audio device, sample rate, buffer size
- **Acceptance:** 5 harmonics playing simultaneously with independently controllable amplitude

### Card 2: Minilab3 MIDI Shaper Mapping
- Extend the secondary MIDI handler (currently only does f₁ mod)
- **Mode 1 — Gain row:** Knobs 1–5 → gain for harmonics 1–5 (active harmonic slots)
- **Mode 2 — Pan row:** Knobs 1–5 → stereo pan for harmonics 1–5
- **Mode 3 — Phase row:** Knobs 1–5 → phase offset 0–360° for harmonics 1–5
- Mode switch: use Minilab3 transport buttons or a dedicated knob
- Sync state bidirectionally with shaper (MIDI→shaper, shaper→display/UI)
- **Acceptance:** Turning Minilab3 knob visibly affects audio in real time

### Card 3: Shaper Control Web UI
- Lightweight local web server (FastAPI + static HTML/JS)
- Shows 5 harmonic "channels" (like a mini mixer): gain fader, pan, phase knob
- WebSocket push: UI always reflects hardware state
- Hardware changes reflect in UI; UI changes are sent to shaper and reflected on hardware (where possible)
- **Acceptance:** UI and Minilab3 stay in sync during live manipulation

### Card 4: OSC + HTTP Automation API
- OSC receiver: `/shaper/harmonic/<n>/gain`, `/shaper/harmonic/<n>/pan`, `/shaper/harmonic/<n>/phase`
- HTTP REST: `PUT /api/harmonic/{n}/params` `{ "gain": 0.8, "pan": -0.5, "phase": 90 }`
- GET: `/api/state` → full parameter snapshot
- POST: `/api/panic` → reset all to defaults
- **Acceptance:** `curl` or Python script can drive the shaper programmatically

### Card 5: Experiment Runner
- `experiments/` directory with experiment scripts (Python)
- API: `Experiment.run()` → time-indexed sequence of parameter states
- Supports: linear sweeps, oscillating sweeps, randomized walks, preset snapshots
- Example: "slowly increase harmonic 3 phase from 0→360° over 10 seconds while recording"
- **Acceptance:** Example experiment runs, produces audible change, logs data

### Card 6: Dataset Logger
- Logs parameter state snapshots at configurable interval (e.g. 100ms)
- Session tagging: `experiment_id`, `timestamp`, `harmonic_n`, `gain`, `pan`, `phase`
- Output: CSV + JSON
- Future: video frame sync markers (for matching cymatic pattern to parameter state)
- **Acceptance:** After a run, a CSV exists with full timestamped parameter history

---

## Codex Review Findings (incorporated)

Codex reviewed the plan and raised the following — addressed below:

**Critical: Phase via Surge XT is likely insufficient**
> Surge XT may not provide sample-accurate, per-harmonic phase-lock behavior via OSC. Phase via note-on is not deterministic across runs.

→ **Plan updated:** Option B (direct Python sine synthesis) is now the **confirmed architecture**. Surge XT stays for its role (listener/reverb) but the shaper synthesizes its own audio. Phase control is only meaningful when we control the synthesis ourselves.

**Risk: GIL/GC pauses and OSC jitter**  
→ The shaper audio engine runs in a `sounddevice` callback (C-level, bypasses GIL). Control messages from Minilab3/UI/API write to a thread-safe parameter store; the audio callback reads it lock-free. OSC/MIDI are supervisory, not hard-real-time.

**Missing: Timing architecture + clock sync**  
→ Added **Card 0b: Timing Architecture & Calibration** (spike). Defines jitter budget, clock sync strategy (monotonic clock for logger), phase calibration loopback.

**Missing: Separation of concerns — real-time vs supervisory**  
→ Explicit in the architecture: audio callback ↔ parameter store ↔ all control surfaces (MIDI/UI/API/runner) are separated by a lock-free ring buffer / shared atomic state.

**Missing: Failure modes**  
→ Added to Card 1: watchdog for audio device disconnection, reconnect strategy, panic/reset path.

**Missing: Experiment data schema with calibration state**  
→ Added to Card 6: run metadata (f₁, harmonic set, calibration snapshot, environmental notes), session ID.

---

## Open Questions for Review

1. **Audio output routing:** Should the shaper output to the same sound card as Surge XT, or a dedicated output? (Assuming same card, different channels or mixed.)
2. **Phase control feasibility:** Phase requires absolute sync of the sine generators. Is `sounddevice` callback-based synthesis precise enough, or do we need a stricter clock?
3. **Minilab3 knob layout:** The Minilab3 has 8 encoders + 8 pads + faders. We should map the 5 harmonic slots to knobs 1–5, with a "parameter page" button. Confirm?
4. **Scope of "5 harmonics":** Are these the first 5 harmonics (n=1,2,3,4,5) always, or the 5 currently latched on the Launchpad?
5. **Surge XT interplay:** Do we want the shaper to fully replace Surge XT for the experiment, or run alongside it (adding fine control on top of the synth output)?

### Resolved by plan
1. **Surge XT phase?** → Not relied on. Direct synthesis handles phase.
2. **Phase accuracy target?** → TBD with Nico after calibration spike. Start with ±5°.
3. **Harmonics as independent voices?** → Yes. Each harmonic_n = one independent sine oscillator with its own gain/pan/phase.
4. **Control update rate?** → MIDI: ~1ms; UI/API: ~16ms (60fps target); runner: configurable (default 100ms steps).
5. **Source of truth?** → `VoiceParameterStore` in shaper process. All inputs write to it; UI/hardware reflect it.
6. **Reproducibility?** → Experiments store full parameter snapshot + calibration state at start of run.
7. **Timestamp sync?** → All logs use `time.monotonic_ns()`. Audio frames tagged with frame count.
8. **Fallback if direct audio fails?** → Degrade to gain-only control via Surge XT velocity; flag phase/pan as unsupported.

---

## Verification Plan

### Automated
- Unit tests: `VoiceParameterStore` CRUD, clamp behavior
- Unit tests: OSC message parsing and routing
- Unit tests: experiment script time-indexing

### Manual Integration
1. Start beacon with `--broadcast`, Launchpad connected
2. Start shaper (`python -m harmonic_shaper.main`)
3. Latch 5 harmonics on Launchpad → shaper detects them via broadcast
4. Turn Minilab3 knob 1 → harmonic 1 gain changes in audio output and UI
5. Run example experiment script → observe time-evolving parameter changes in audio + dataset log
