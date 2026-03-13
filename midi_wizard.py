#!/usr/bin/env python3
"""
Minilab3 CC Mapping Wizard
Walks through each control, records the CC, writes config.py.

Usage:  python midi_wizard.py
"""

import queue
import re
import sys
import threading
import time

try:
    import mido
except ImportError:
    print("ERROR: mido not installed.  pip install mido python-rtmidi")
    sys.exit(1)

CONFIG_PATH = "harmonic_shaper/config.py"

CONTROLS = [
    ("Slider 1", "slider", 0),
    ("Slider 2", "slider", 1),
    ("Slider 3", "slider", 2),
    ("Slider 4", "slider", 3),
    ("Knob 1",   "pan",    0),
    ("Knob 2",   "pan",    1),
    ("Knob 3",   "pan",    2),
    ("Knob 4",   "pan",    3),
    ("Knob 5",   "phase",  0),
    ("Knob 6",   "phase",  1),
    ("Knob 7",   "phase",  2),
    ("Knob 8",   "phase",  3),
]


# ── MIDI reader thread ─────────────────────────────────────────────────────────

cc_queue: queue.Queue[int] = queue.Queue()
stop_event = threading.Event()


def midi_reader(port_name: str) -> None:
    with mido.open_input(port_name) as port:
        while not stop_event.is_set():
            msg = port.receive(block=False)
            if msg and msg.type == "control_change":
                cc_queue.put(msg.control)
            else:
                time.sleep(0.005)


# ── Helpers ───────────────────────────────────────────────────────────────────

def drain_queue() -> None:
    """Empty whatever is buffered."""
    while not cc_queue.empty():
        try:
            cc_queue.get_nowait()
        except queue.Empty:
            break


def wait_cc(timeout: float = 20.0) -> int | None:
    """Block until a CC arrives (or timeout)."""
    try:
        return cc_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def find_port(pattern: str = "minilab") -> str | None:
    for name in mido.get_input_names():
        if pattern.lower() in name.lower():
            return name
    return None


def update_config(slider_ccs, pan_ccs, phase_ccs) -> None:
    with open(CONFIG_PATH) as f:
        src = f.read()

    def replace_list(text, varname, values):
        pat = rf"({re.escape(varname)}\s*=\s*)\[.*?\]"
        return re.sub(pat, r"\g<1>" + str(values), text)

    src = replace_list(src, "MINILAB_SLIDER_CCS", slider_ccs)
    src = replace_list(src, "MINILAB_PAN_CCS",    pan_ccs)
    src = replace_list(src, "MINILAB_PHASE_CCS",  phase_ccs)

    with open(CONFIG_PATH, "w") as f:
        f.write(src)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    port_name = find_port()
    if not port_name:
        print("Minilab not found. Available ports:")
        for n in mido.get_input_names():
            print(f"  {n}")
        sys.exit(1)

    print(f"\nConnected: {port_name}")
    print("─" * 50)

    # Start MIDI reader in background
    t = threading.Thread(target=midi_reader, args=(port_name,), daemon=True)
    t.start()

    mapping: dict[str, int] = {}

    for label, group, idx in CONTROLS:
        while True:
            drain_queue()
            print(f"\n  → Touch {label} now (move it fully)...")

            cc = wait_cc(timeout=20.0)
            if cc is None:
                print("    Timed out. Skipping.")
                mapping[label] = -1
                break

            # Drain any extra messages from the same gesture
            time.sleep(0.2)
            drain_queue()

            answer = input(f"    Detected CC {cc}. OK? [Enter=yes / r=retry]: ").strip().lower()
            if answer == "r":
                continue
            mapping[label] = cc
            break

    stop_event.set()

    # ── Summary ──
    print("\n─── Mapping results ──────────────────────────────────")
    for label, cc in mapping.items():
        print(f"  {label:<10} CC {cc}")

    slider_ccs = [mapping[f"Slider {i+1}"] for i in range(4)]
    pan_ccs    = [mapping[f"Knob {i+1}"]   for i in range(4)]
    phase_ccs  = [mapping[f"Knob {i+5}"]   for i in range(4)]

    print(f"\n  MINILAB_SLIDER_CCS = {slider_ccs}")
    print(f"  MINILAB_PAN_CCS    = {pan_ccs}")
    print(f"  MINILAB_PHASE_CCS  = {phase_ccs}")

    if any(v == -1 for v in slider_ccs + pan_ccs + phase_ccs):
        print("\nSome controls missing — config NOT updated.")
        sys.exit(1)

    update_config(slider_ccs, pan_ccs, phase_ccs)
    print(f"\n  config.py updated.")


if __name__ == "__main__":
    main()
