import mido
import time
import argparse

def inspect_midi(port_filter=None):
    print("Listing available MIDI ports...")
    inputs = mido.get_input_names()
    for name in inputs:
        print(f"  - {name}")

    if not inputs:
        print("No MIDI input ports found.")
        return

    # Auto-select port
    port_name = inputs[0]
    if port_filter:
        matches = [n for n in inputs if port_filter.lower() in n.lower()]
        if matches:
            port_name = matches[0]
        else:
            print(f"No port matching '{port_filter}' found. Using '{port_name}'")

    print(f"\nListening on '{port_name}'...")
    print("Press Ctrl+C to stop.")
    
    try:
        with mido.open_input(port_name) as port:
            for msg in port:
                print(f"RECV: {msg}")
    except KeyboardInterrupt:
        print("\nStopping...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", help="Port name filter (e.g. 'Force')")
    args = parser.parse_args()
    inspect_midi(args.filter)
