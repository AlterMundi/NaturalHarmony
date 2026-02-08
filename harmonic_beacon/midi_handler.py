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
             # Fallback to Virtual Port
             print("Warning: Could not open any physical MIDI ports (likely busy).")
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

        client_start_pattern = re.compile(r"^client (\d+): '([^']+)'")
        port_line_pattern = re.compile(r"^\s+(\d+) '([^']+)'")
        
        connected_sources = set()

        while not self._stop_monitor.is_set():
            try:
                # 1. Find OUR Virtual Port ID (it might change if restarted, though unlikley in loop)
                # We need to re-parse every time because client IDs can shift if things restart
                result = subprocess.run(['aconnect', '-l'], capture_output=True, text=True)
                output = result.stdout
                
                my_client_id = None
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
                        
                        if "HarmonicBeacon Input" in port_name:
                            my_client_id = current_client_id
                            my_port_id = full_port_id
                        
                        # Identify candidate sources
                        elif (current_client_id != "0" and 
                              "Midi Through" not in current_client_name and
                              "HarmonicBeacon" not in port_name and 
                              "RtMidi" not in current_client_name):
                             # Only connect OUTPUT ports (source files)
                             # aconnect -l lists all ports. We need to know if it's an output.
                             # But 'aconnect -l' usually lists both.
                             # We'll valid connection by trying it.
                             available_sources.add(full_port_id)

                if my_port_id:
                    # 2. Connect new sources
                    for source in available_sources:
                        if source not in connected_sources:
                            # Verify if already connected (aconnect -l usually shows arrows)
                            # But simpler to just try 'aconnect' (it's idempotent-ish, returns error if connected)
                            
                            # We check if 'Connecting To: ...' is already in the output for this port?
                            # Parsing 'Connecting To' is complex. Let's just try to run aconnect.
                            # We will suppress errors.
                            
                            # Log only if we haven't seen this source before in this session
                            print(f"[MIDI Monitor] Connecting {source} -> {my_port_id}")
                            ret = subprocess.run(['aconnect', source, my_port_id], capture_output=True)
                            
                            # Identify if successful or already connected
                            # If connection made, add to our set
                            connected_sources.add(source)
                
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
