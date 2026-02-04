
import mido
import time
import sys


def get_force_ports():
    ports = []
    outputs = mido.get_output_names()
    for name in outputs:
        if "Force" in name:
            ports.append(name)
    return ports

def test_lights():
    print("🔍 Looking for Akai Force MIDI Ports...")
    ports = get_force_ports()
    
    if not ports:
        print("❌ Could not find ANY Akai Force port!")
        print(f"Available ports: {mido.get_output_names()}")
        return

    print(f"✓ Found Ports: {ports}")
    
    for port_name in ports:
        print(f"\n════════════════════════════════════════════════════")
        print(f"🚀 TESTING PORT: {port_name}")
        print(f"════════════════════════════════════════════════════")
        
        try:
            with mido.open_output(port_name) as out:
                # Strategy 1: Channel Scan
                print("\n--- Strategy 1: Channel Scan (Velocity 3) ---")
                TEST_NOTE = 110 # Bottom Left
                for ch in range(16):
                    print(f"  > Ch {ch}...", end=" ", flush=True)
                    out.send(mido.Message('note_on', note=TEST_NOTE, velocity=3, channel=ch))
                    time.sleep(0.1)
                    out.send(mido.Message('note_off', note=TEST_NOTE, velocity=0, channel=ch))
                print()
                    
                # Strategy 2: Velocity Color Scan (Channel 9 & 0)
                print("\n--- Strategy 2: Velocity Scan (Ch 9 & 0) ---")
                velocities = [1, 3, 5, 10, 60, 127]
                for vel in velocities:
                    print(f"  > Vel {vel}...", end=" ", flush=True)
                    out.send(mido.Message('note_on', note=TEST_NOTE, velocity=vel, channel=9))
                    time.sleep(0.2)
                    out.send(mido.Message('note_off', note=TEST_NOTE, velocity=0, channel=9))
                    out.send(mido.Message('note_on', note=TEST_NOTE, velocity=vel, channel=0))
                    time.sleep(0.2)
                    out.send(mido.Message('note_off', note=TEST_NOTE, velocity=0, channel=0))
                print()
                
                # Strategy 3: Note Range Sweep (Fast)
                print("\n--- Strategy 3: Note Sweep (0-127) Ch 9 ---")
                for n in range(0, 128, 8):
                    out.send(mido.Message('note_on', note=n, velocity=3, channel=9))
                    time.sleep(0.02)
                    out.send(mido.Message('note_off', note=n, velocity=0, channel=9))
                
        except Exception as e:
            print(f"❌ Error on port {port_name}: {e}")

if __name__ == "__main__":
    test_lights()
