#!/usr/bin/env python3
"""
Minilab3 CC Discovery Tool
--------------------------
Run this, then touch each physical control (knobs, sliders, pads) one at a time.
It prints the CC number and value so you can build the correct config table.

Usage:
    python midi_monitor.py
    python midi_monitor.py --port "Minilab"   # substring match, default
"""

import argparse
import sys

try:
    import mido
except ImportError:
    print("ERROR: mido not installed. Run: pip install mido python-rtmidi")
    sys.exit(1)

# ── Known CC table (current config, for comparison) ────────────────────────
KNOWN = {
    # Sliders
    73: "Slider 1", 75: "Slider 2", 79: "Slider 3", 72: "Slider 4",
    # Knobs top row
    74: "Knob 1 (top)", 71: "Knob 2 (top)", 76: "Knob 3 (top)", 77: "Knob 4 (top)",
    # Knobs bottom row
    93: "Knob 5 (bot)", 18: "Knob 6 (bot)", 19: "Knob 7 (bot)", 16: "Knob 8 (bot)",
}

seen: dict[int, tuple[int, int]] = {}   # cc → (min_val, max_val)
seen_notes: set[int] = set()


def find_port(pattern: str) -> str | None:
    for name in mido.get_input_names():
        if pattern.lower() in name.lower():
            return name
    return None


def handle(msg) -> None:
    if msg.type == "control_change":
        cc, val = msg.control, msg.value
        prev = seen.get(cc)
        if prev is None:
            seen[cc] = (val, val)
            label = KNOWN.get(cc, "*** UNKNOWN ***")
            print(f"  CC {cc:3d}  val={val:3d}   ← {label}")
        else:
            lo, hi = prev
            lo, hi = min(lo, val), max(hi, val)
            seen[cc] = (lo, hi)
            label = KNOWN.get(cc, "*** UNKNOWN ***")
            print(f"  CC {cc:3d}  val={val:3d}   range [{lo}–{hi}]   {label}")

    elif msg.type in ("note_on", "note_off"):
        note = msg.note
        if note not in seen_notes:
            seen_notes.add(note)
            kind = "note_on" if msg.type == "note_on" else "note_off"
            print(f"  NOTE {note:3d}  vel={msg.velocity:3d}   ({kind})  ← pad/key")


def print_summary() -> None:
    print("\n─── Summary ───────────────────────────────────────────")
    print(f"{'CC':>5}  {'range':>10}  label")
    for cc, (lo, hi) in sorted(seen.items()):
        label = KNOWN.get(cc, "*** UNKNOWN ***")
        print(f"  {cc:3d}  [{lo:3d}–{hi:3d}]    {label}")
    if seen_notes:
        print(f"\nPad/key notes seen: {sorted(seen_notes)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minilab3 CC discovery tool")
    parser.add_argument("--port", default="Minilab", help="Port name substring (default: Minilab)")
    parser.add_argument("--list", action="store_true", help="List available MIDI ports and exit")
    args = parser.parse_args()

    if args.list:
        print("Available MIDI input ports:")
        for name in mido.get_input_names():
            print(f"  {name}")
        return

    port_name = find_port(args.port)
    if not port_name:
        print(f"ERROR: No port matching '{args.port}' found.")
        print("Available ports:")
        for name in mido.get_input_names():
            print(f"  {name}")
        sys.exit(1)

    print(f"Listening on: {port_name}")
    print("Touch each control to identify its CC number. Ctrl+C to stop.\n")
    print(f"  {'MSG':>8}  {'val':>5}   label")
    print("  " + "─" * 50)

    try:
        with mido.open_input(port_name) as port:
            for msg in port:
                handle(msg)
    except KeyboardInterrupt:
        print_summary()


if __name__ == "__main__":
    main()
