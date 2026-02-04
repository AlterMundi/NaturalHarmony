
import mido
import time

def get_launchpad_ports():
    ports = []
    outputs = mido.get_output_names()
    for name in outputs:
        if "Launchpad" in name or "Mini" in name:
            ports.append(name)
    return ports

def test_launchpad():
    print("🔍 Looking for Novation Launchpad Ports...")
    ports = get_launchpad_ports()
    
    if not ports:
        print("❌ Could not find any port with 'Launchpad' or 'Mini' in the name!")
        print(f"Available ports: {mido.get_output_names()}")
        return

    print(f"✓ Found Ports: {ports}")
    
    for port_name in ports:
        print(f"\n════════════════════════════════════════════════════")
        print(f"🚀 TESTING PORT: {port_name}")
        print(f"════════════════════════════════════════════════════")
        
        try:
            with mido.open_output(port_name) as out:
                print("\n--- Test 1: Lighting All Pads (Note Sweep 0-127) ---")
                print("  > Sending Velocity 60 (Green/Bright) on Channel 0...")
                
                # Try Channel 0 (Standard) and Channel 8 (User 2 on some models)
                for channel in [0, 8]:
                    print(f"  > Testing Channel {channel}...")
                    for n in range(128):
                        out.send(mido.Message('note_on', note=n, velocity=60, channel=channel))
                        time.sleep(0.02)
                        
                    # Turn off
                    print("  > Turning off...")
                    for n in range(128):
                        out.send(mido.Message('note_off', note=n, channel=channel))
                
                print("\n✅ Port Test Complete.")
                
        except Exception as e:
            print(f"❌ Error on port {port_name}: {e}")

if __name__ == "__main__":
    test_launchpad()
