import mido
import subprocess
import os

print("-" * 40)
print("MIDI DIAGNOSTICS")
print("-" * 40)

# 1. Check Mido/RtMidi APIs
try:
    print(f"Mido Backend: {mido.backend.name}")
    import rtmidi
    apis = rtmidi.get_compiled_api()
    print("Compiled RtMidi APIs:")
    for api in apis:
        print(f" - {rtmidi.get_api_name(api)}")
except Exception as e:
    print(f"Error checking RtMidi: {e}")

print("\n" + "-" * 20 + "\n")

# 2. Check ALSA Ports
print("ALSA Ports (aconnect -l):")
try:
    subprocess.run(["aconnect", "-l"])
except FileNotFoundError:
    print("aconnect not found")

print("\n" + "-" * 20 + "\n")

# 3. Check JACK Ports (if available)
print("JACK Ports (jack_lsp):")
try:
    subprocess.run(["jack_lsp", "-c"])
except FileNotFoundError:
    print("jack_lsp not found")

print("\n" + "-" * 20 + "\n")

# 4. Check a2jmidid process
print("a2jmidid process:")
subprocess.run(["ps", "-ef", "|", "grep", "a2jmidid"], shell=True)
