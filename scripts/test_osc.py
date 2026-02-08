#!/usr/bin/env python3
"""Test script to verify OSC connection to Surge XT.

Run this script to send test notes to Surge XT and verify the connection.
Make sure to:
1. UNCHECK KeyLab in Surge XT's MIDI inputs (Audio/MIDI Settings)
2. Enable OSC in Surge XT (Menu → OSC settings → Show OSC Settings)
3. Set OSC In Port to 53280 (default) or match our config
"""

import time
import sys

# Add parent to path
sys.path.insert(0, '/home/nicolas/OS_projects/NaturalHarmony')

from harmonic_beacon import config

try:
    from pythonosc import udp_client
except ImportError:
    print("ERROR: python-osc not installed. Run: pip install python-osc")
    sys.exit(1)


def test_osc_connection():
    """Send test OSC messages to Surge XT using correct format."""
    
    print(f"OSC Test Script for Surge XT")
    print(f"=" * 50)
    print(f"Target: {config.OSC_HOST}:{config.OSC_PORT}")
    print()
    print("Surge XT OSC Format (v1.3+):")
    print("  /fnote frequency velocity [noteID]")
    print("  /fnote/rel frequency velocity [noteID]")
    print("  All values must be FLOATS!")
    print()
    
    # Create OSC target
    client = udp_client.SimpleUDPClient(config.OSC_HOST, config.OSC_PORT)
    
    # Test 1: Simple frequency note
    print("Test 1: Playing A4 (440 Hz) for 1 second...")
    print("  Sending: /fnote 440.0 100.0")
    client.send_message("/fnote", [440.0, 100.0])
    time.sleep(1.0)
    print("  Sending: /fnote 440.0 0.0  (velocity 0 = note off)")
    client.send_message("/fnote", [440.0, 0.0])
    time.sleep(0.5)
    
    # Test 2: Frequency note with noteID
    print("\nTest 2: Playing C4 (261.63 Hz) with noteID for 1 second...")
    note_id = 12345.0
    print(f"  Sending: /fnote 261.63 100.0 {note_id}")
    client.send_message("/fnote", [261.63, 100.0, note_id])
    time.sleep(1.0)
    print(f"  Sending: /fnote/rel 261.63 0.0 {note_id}")
    client.send_message("/fnote/rel", [261.63, 0.0, note_id])
    time.sleep(0.5)
    
    # Test 3: Harmonic series demonstration
    print("\nTest 3: Playing harmonic series (f₁=54 Hz)...")
    f1 = 54.0
    harmonics = [1, 3, 5, 7, 9]  # Fundamental, 5th, 3rd, 7th, 9th
    for n in harmonics:
        freq = f1 * n
        print(f"  Harmonic {n}: {freq:.1f} Hz")
        client.send_message("/fnote", [freq, 100.0])
        time.sleep(0.4)
        client.send_message("/fnote", [freq, 0.0])
        time.sleep(0.1)
    
    # Test 4: All notes off
    print("\nTest 4: Sending /allnotesoff...")
    client.send_message("/allnotesoff", [])
    
    print("\n" + "=" * 50)
    print("Did you hear the notes?")
    print()
    print("If YES: OSC is working! Run the full app:")
    print("  python -m harmonic_beacon.main")
    print()
    print("If NO, check:")
    print("  1. Surge XT is running and OSC is enabled")
    print("  2. OSC In Port matches our config (currently", config.OSC_PORT, ")")
    print("  3. KeyLab is UNCHECKED in Surge XT MIDI settings")
    print("  4. Surge XT shows some activity in the oscilloscope")


if __name__ == "__main__":
    test_osc_connection()
