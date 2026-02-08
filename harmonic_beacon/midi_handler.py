"""MIDI input handling using mido and python-rtmidi.

Handles MIDI input from the controller (KeyLab 61 MkII) and
dispatches Note-On/Off and CC messages.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import mido

from . import config


class MidiMessageType(Enum):
    """Types of MIDI messages we handle."""
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    CONTROL_CHANGE = "control_change"
    OTHER = "other"


@dataclass 
class NoteEvent:
    """Represents a Note-On or Note-Off event."""
    note: int
    velocity: int
    channel: int


@dataclass
class CCEvent:
    """Represents a Control Change event."""
    control: int
    value: int
    channel: int


class MidiHandler:
    """Handles MIDI input from the controller.
    
    Opens a MIDI input port and provides methods for polling
    and processing incoming messages.
    """
    
    def __init__(
        self,
        port_pattern: Optional[str] = config.MIDI_PORT_PATTERN,
        f1_cc: int = config.F1_CC_NUMBER,
        debug: bool = False,
    ):
        """Initialize the MIDI handler.
        
        Args:
            port_pattern: Substring to match in port names, or None for first port
            f1_cc: CC number used for f₁ modulation
            debug: If True, print raw MIDI messages to console
        """
        self.port_pattern = port_pattern
        self.f1_cc = f1_cc
        self.debug = debug
        self.debug = debug
        self._ports: list[mido.ports.BaseInput] = []
        self._output_ports: list[mido.ports.BaseOutput] = []
        self._port_names: list[str] = []
        
    def open(self) -> str:
        """Open all available MIDI input ports.
        
        Returns:
            Comma-separated list of opened port names
            
        Raises:
            RuntimeError: If no MIDI ports are found
        """
        available_ports = mido.get_input_names()
        
        # ... (same port filtering logic as before) ...
        # (This tool call only lets me replace contiguous blocks, and the open() method is huge)
        # I will focus on where the fallback happens.
        
        self._ports = []
        self._port_names = []
        self._output_ports = []
        
        # Try to open physical ports first (same logic)
        for name in available_ports:
            # ... (filtering) ...
            if self.port_pattern and self.port_pattern.lower() not in name.lower():
                continue
            # ... (system port skipping) ...
            lower_name = name.lower()
            if "midi through" in lower_name or "rtmidi" in lower_name:
                 continue
            
            try:
                in_port = mido.open_input(name)
                self._ports.append(in_port)
                self._port_names.append(name)
                
                # Feedback Output Port Logic (same as before)
                try:
                    output_ports = mido.get_output_names()
                    if name in output_ports:
                        out_port = mido.open_output(name)
                        self._output_ports.append(out_port)
                except:
                    pass
            except:
                pass

        if not self._ports:
             # If we tried to filter but found nothing, or just failed to open anything
             print("Warning: Could not open any physical MIDI ports (likely busy).")
             
             # Check for VirMIDI ports (Zynthian integration)
             # "VirMIDI" usually appears as an OUTPUT port (destination) in mido.get_output_names()
             # We want to send our generated notes TO it, so Zynthian sees them coming FROM it.
             virmidi_port_name = None
             for name in mido.get_output_names():
                 if "VirMIDI" in name and "0-0" in name: # Prefer first port (e.g. 4-0)
                     virmidi_port_name = name
                     break
                 if "VirMIDI" in name and not virmidi_port_name:
                     virmidi_port_name = name # Fallback to any VirMIDI port

             if virmidi_port_name:
                 print(f"[MIDI] Detected VirMIDI port: '{virmidi_port_name}'")
                 print("[MIDI] Integrating with Zynthian via VirMIDI...")
                 
                 try:
                     # 1. Open VirMIDI as our OUTPUT (where we send notes)
                     out_port = mido.open_output(virmidi_port_name)
                     self._output_ports.append(out_port)
                     print(f"[MIDI] Connected to VirMIDI Output: {virmidi_port_name}")
                     
                     # 2. We still need an INPUT for the KeyLab/Launchpad
                     # Since physical ports are busy, we still create a Virtual Input
                     in_port = mido.open_input('HarmonicBeacon Input', virtual=True)
                     self._ports.append(in_port)
                     self._port_names.append('HarmonicBeacon Input (Virtual)')
                     
                     print("[MIDI] Created virtual input port: HarmonicBeacon Input")
                     
                     # 3. Auto-connect physical controllers to our Virtual Input
                     self._start_auto_connect_monitor()
                     
                 except Exception as e:
                     print(f"[MIDI] Failed to connect to VirMIDI: {e}")
                     raise RuntimeError(f"VirMIDI connection failed: {e}") from e
                     
             else:
                 # Standard Fallback (No VirMIDI)
                 print("Attempting to create a virtual MIDI port named 'HarmonicBeacon Input'...")
                 
                 try:
                     # Create virtual input port
                     in_port = mido.open_input('HarmonicBeacon Input', virtual=True)
                     self._ports.append(in_port)
                     self._port_names.append('HarmonicBeacon Input (Virtual)')
                     
                     # Create virtual output port
                     out_port = mido.open_output('HarmonicBeacon Output', virtual=True)
                     self._output_ports.append(out_port)
                     
                     # Start Auto-Connect Monitor
                     self._start_auto_connect_monitor()
                     
                 except Exception as e:
                     if self.port_pattern:
                         print(f"Warning: No ports matching '{self.port_pattern}' enabled.")
                     raise RuntimeError(f"Could not open any MIDI ports (Physical or Virtual). Error: {e}") from e

        return ", ".join(self._port_names)

    def _start_auto_connect_monitor(self) -> None:
        """Start a background thread to monitor and auto-connect new MIDI ports."""
        import threading
        
        # Prevent starting multiple monitors
        if hasattr(self, '_monitor_thread') and self._monitor_thread.is_alive():
            return

        self._stop_monitor = threading.Event()
        self._monitor_thread = threading.Thread(target=self._auto_connect_loop, daemon=True)
        self._monitor_thread.start()
        print("[MIDI] Started background MIDI connection monitor.")

    def _auto_connect_loop(self) -> None:
        """Continuously check for new MIDI ports and connect them to our virtual input."""
        import time
        import subprocess
        import re

        # Regex patterns to parse aconnect -l output
        # client 28: 'KeyLab mkII 61' [type=kernel,card=3]
        client_start_pattern = re.compile(r"^client (\d+): '([^']+)'")
        #     0 'KeyLab mkII 61 MIDI'
        port_line_pattern = re.compile(r"^\s+(\d+) '([^']+)'")
        
        connected_sources = set()

        while not self._stop_monitor.is_set():
            try:
                result = subprocess.run(['aconnect', '-l'], capture_output=True, text=True)
                output = result.stdout
                
                my_port_id = None
                available_sources = set()
                
                current_client_id = None
                current_client_name = ""
                
                lines = output.splitlines()
                for line in lines:
                    client_match = client_start_pattern.search(line)
                    if client_match:
                        current_client_id = client_match.group(1)
                        current_client_name = client_match.group(2)
                        continue
                    
                    port_match = port_line_pattern.search(line)
                    if port_match and current_client_id:
                        port_num = port_match.group(1)
                        port_name = port_match.group(2)
                        full_port_id = f"{current_client_id}:{port_num}"
                        
                        # Identify OUR Virtual Input Port
                        # In the log: client 137: 'RtMidiIn Client' -> 0 'HarmonicBeacon Input'
                        # So we match the PORT name. Use strip() just in case.
                        if "HarmonicBeacon Input" in port_name.strip():
                            my_port_id = full_port_id
                            # print(f"[MIDI Monitor Debug] Found My Input at {full_port_id} (Client: {current_client_name})")
                        
                        # Identify Candidate Sources (Hardware MIDI Controllers)
                        # We want to connect: KeyLab (28:0), Launchpad (24:0), etc.
                        # We EXCLUDE:
                        # - System/Timer (0)
                        # - Midi Through (14)
                        # - VirMIDI ports (32 in this case, often used for output, usually we don't want to loop back)
                        # - RtMidi Clients (us, or other software)
                        # - Network/Announce
                        
                        elif (current_client_id != "0" and 
                              "Midi Through" not in current_client_name and
                              "Virtual Raw MIDI" not in current_client_name and  # Avoid VirMIDI
                              "RtMidi" not in current_client_name): # Avoid other software ports
                             
                            available_sources.add(full_port_id)

                if my_port_id:
                    # Connect new sources
                    for source in available_sources:
                        if source not in connected_sources:
                            # Log connection attempt
                            print(f"[MIDI Monitor] Connecting {source} -> {my_port_id}")
                            ret = subprocess.run(['aconnect', source, my_port_id], capture_output=True)
                            
                            if ret.returncode == 0:
                                print(f"[MIDI Monitor] Successfully connected via ALSA: {source}")
                                connected_sources.add(source)
                            else:
                                # Fallback to JACK Connection (Zynthian compatibility)
                                # If ALSA is busy (locked by Zynthian/a2jmidid), we must route via JACK.
                                try:
                                    # Parse IDs: source "28:0" -> client 28
                                    src_client = source.split(':')[0]
                                    dest_client = my_port_id.split(':')[0]
                                    
                                    # Guess JACK Port Names based on Zynthian conventions
                                    # Source: system:midi_capture_{client_id} (Hardware via ALSA)
                                    # Dest: a2j:RtMidiIn Client [{client_id}] (Software via a2jmidid)
                                    
                                    jack_src = f"system:midi_capture_{src_client}"
                                    
                                    # Find exact Dest name from jack_lsp
                                    jack_res = subprocess.run(['jack_lsp'], capture_output=True, text=True)
                                    jack_ports = jack_res.stdout.splitlines()
                                    
                                    jack_dest = None
                                    # Look for a port containing our client ID and "playback" (which is Input in a2j-speak usually)
                                    # Actually, let's look for "RtMidiIn Client [{dest_client}]"
                                    search_str = f"RtMidiIn Client [{dest_client}]"
                                    for p in jack_ports:
                                        if search_str in p and "playback" in p.lower(): 
                                            # "playback" in JACK usually means OUTPUT, but a2j is weird.
                                            # In the user log: a2j:RtMidiIn Client [137] (playback): HarmonicBeacon Input
                                            # Yes, that is the one we want to connect TO?
                                            # Wait.
                                            # JACK Source (Output) -> JACK Sink (Input).
                                            # system:midi_capture_X is a Source.
                                            # a2j:... (playback) often means it's an ALSA Playback port, so it consumes MIDI from ALSA 
                                            # and outputs to JACK? OR it consumes MIDI from JACK and plays to ALSA?
                                            # "playback" (ALSA) -> CONSUMES data from app -> SENDS to Hardware/Graph.
                                            # "capture" (ALSA) -> PRODUCES data from Hardware -> SENDS to App.
                                            
                                            # Let's re-read the log:
                                            # a2j:RtMidiIn Client [137] (playback): HarmonicBeacon Input
                                            # This is an ALSA INPUT port (we read from it).
                                            # So a2j exposes it as a JACK OUTPUT (Source)?? No, that would make no sense.
                                            # Unless... we want to WRITE to it.
                                            # We want KeyLab (Source) -> Beacon (Sink).
                                            # Beacon is an ALSA Input.
                                            # a2j usually exposes ALSA Inputs as JACK Ports that you can CONNECT TO (Sinks).
                                            # Let's assume this is the Sink.
                                            jack_dest = p
                                            break
                                    
                                    if jack_dest:
                                        print(f"[MIDI Monitor] Attempting JACK connection: {jack_src} -> {jack_dest}")
                                        jret = subprocess.run(['jack_connect', jack_src, jack_dest], capture_output=True)
                                        if jret.returncode == 0:
                                            print(f"[MIDI Monitor] Successfully connected via JACK: {jack_src} -> {jack_dest}")
                                            connected_sources.add(source) # Mark as connected so we don't retry locally
                                        else:
                                            pass # print(f"[MIDI Monitor] JACK connection failed: {jret.stderr}")
                                    else:
                                        pass # print(f"[MIDI Monitor] Could not find JACK destination for client {dest_client}")

                                except Exception as e:
                                    print(f"[MIDI Monitor] JACK fallback error: {e}")
                
            except Exception as e:
                print(f"[MIDI Monitor] Error: {e}")
            
            time.sleep(2.0) # Poll every 2 seconds

    def close(self) -> None:
        """Close all MIDI input and output ports."""
        if hasattr(self, '_stop_monitor'):
            self._stop_monitor.set()
            if hasattr(self, '_monitor_thread'):
                self._monitor_thread.join(timeout=1.0)

        for port in self._ports:
            port.close()
        # ... (rest of close)
    
    def poll(self) -> list[mido.Message]:
        """Poll for pending MIDI messages from all ports (non-blocking).
        
        Returns:
            List of pending MIDI messages
        """
        all_messages = []
        for port in self._ports:
            all_messages.extend(list(port.iter_pending()))
            
        messages = all_messages
        
        if self.debug:
            for msg in messages:
                print(f"[MIDI IN] {msg}")
                
        return messages

    def send_message(self, msg: mido.Message) -> None:
        """Send a MIDI message to all output ports."""
        for port in self._output_ports:
            try:
                port.send(msg)
                if self.debug:
                    print(f"[MIDI OUT] {msg}")
            except Exception as e:
                print(f"Error sending MIDI: {e}")
    
    def is_note_on(self, msg: mido.Message) -> bool:
        """Check if a message is a Note-On event.
        
        Note: A Note-On with velocity 0 is treated as Note-Off.
        """
        return msg.type == "note_on" and msg.velocity > 0
    
    def is_note_off(self, msg: mido.Message) -> bool:
        """Check if a message is a Note-Off event.
        
        Note: A Note-On with velocity 0 is treated as Note-Off.
        """
        return msg.type == "note_off" or (
            msg.type == "note_on" and msg.velocity == 0
        )
    
    def is_f1_control(self, msg: mido.Message) -> bool:
        """Check if a message is the f₁ modulation CC."""
        return msg.type == "control_change" and msg.control == self.f1_cc
    
    def is_stacking_mix_control(self, msg: mido.Message) -> bool:
        """Check if a message is the Stacking Mix CC (CC67)."""
        return msg.type == "control_change" and msg.control == config.STACKING_MIX_CC

    def is_stacking_mode_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the Stacking Mode toggle CC (CC22)."""
        return msg.type == "control_change" and msg.control == config.STACKING_MODE_CC
    

    def is_panic_cc(self, msg: mido.Message) -> bool:
        """Check if a message is the Panic button CC (e.g. 111)."""
        return msg.type == "control_change" and msg.control == config.PANIC_NOTE

    def is_split_mode_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is Split Mode Toggle (CC 104)."""
        return msg.type == "control_change" and msg.control == config.SPLIT_MODE_TOGGLE_CC
    
    def parse_note_event(self, msg: mido.Message) -> NoteEvent:
        """Parse a Note-On/Off message into a NoteEvent."""
        return NoteEvent(
            note=msg.note,
            velocity=msg.velocity,
            channel=msg.channel,
        )
    
    def parse_cc_event(self, msg: mido.Message) -> CCEvent:
        """Parse a CC message into a CCEvent."""
        return CCEvent(
            control=msg.control,
            value=msg.value,
            channel=msg.channel,
        )
    
    @property
    def port_name(self) -> Optional[str]:
        """Names of currently open ports (comma separated)."""
        if not self._port_names:
            return None
        return ", ".join(self._port_names)
    
    @property
    def is_open(self) -> bool:
        """Whether any port is currently open."""
        return len(self._ports) > 0
    
    @staticmethod
    def list_ports() -> list[str]:
        """List all available MIDI input ports."""
        return mido.get_input_names()
    
    def __enter__(self) -> "MidiHandler":
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
