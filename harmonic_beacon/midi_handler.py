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
        
        if not available_ports:
            raise RuntimeError("No MIDI input ports available")
        
        self._ports = []
        self._port_names = []
        self._output_ports = []
        
        # Iterate over all available ports
        for name in available_ports:
            # If a pattern is specified, skip non-matching ports
            if self.port_pattern and self.port_pattern.lower() not in name.lower():
                continue

            # Prevent feedback loops by ignoring system passthrough ports
            lower_name = name.lower()
            if "midi through" in lower_name or "rtmidi" in lower_name:
                 if self.debug:
                     print(f"[MIDI] Skipping potential loopback port: {name}")
                 continue
                
            try:
                # Open input port
                in_port = mido.open_input(name)
                self._ports.append(in_port)
                self._port_names.append(name)
                if self.debug:
                    print(f"[MIDI] Opened input port: {name}")

                # Try to open output port with same name for feedback
                try:
                    output_ports = mido.get_output_names()
                    # Try exact match first
                    if name in output_ports:
                        out_port = mido.open_output(name)
                        self._output_ports.append(out_port)
                        if self.debug:
                            print(f"[MIDI] Opened output port: {name}")
                    else:
                        # Try approximate match
                        for out_name in output_ports:
                            if name[:-2] in out_name: # Simple heuristic
                                out_port = mido.open_output(out_name)
                                self._output_ports.append(out_port)
                                if self.debug:
                                    print(f"[MIDI] Opened output port (approx): {out_name}")
                                break
                except Exception as e:
                    if self.debug:
                        print(f"[MIDI] Could not open output port for {name}: {e}")
                        
            except Exception as e:
                print(f"[MIDI] Error opening port {name}: {e}")

        if not self._ports:
             # If we tried to filter but found nothing, or just failed to open anything
             print("Warning: Could not open any physical MIDI ports (likely busy).")
             print("Attempting to create a virtual MIDI port named 'HarmonicBeacon Input'...")
             
             try:
                 # Create virtual input port
                 in_port = mido.open_input('HarmonicBeacon Input', virtual=True)
                 self._ports.append(in_port)
                 self._port_names.append('HarmonicBeacon Input (Virtual)')
                 print("[MIDI] Created virtual input port: HarmonicBeacon Input")
                 
                 # Create virtual output port
                 out_port = mido.open_output('HarmonicBeacon Output', virtual=True)
                 self._output_ports.append(out_port)
                 print("[MIDI] Created virtual output port: HarmonicBeacon Output")
                 
                 # Attempt to auto-connect physical ports to our virtual port
                 self._auto_connect_virtual_ports()
                 
             except Exception as e:
                 print(f"[MIDI] Failed to create virtual port: {e}")
                 if self.port_pattern:
                     print(f"Warning: No ports matching '{self.port_pattern}' enabled.")
                 raise RuntimeError(f"Could not open any MIDI ports (Physical or Virtual). Error: {e}") from e

        return ", ".join(self._port_names)

    def _auto_connect_virtual_ports(self) -> None:
        """Automatically connect matching physical MIDI outputs to our virtual input using aconnect."""
        try:
            import subprocess
            import re
            
            print("[MIDI] Auto-connecting physical ports to HarmonicBeacon...")
            
            # Get list of clients from aconnect
            result = subprocess.run(['aconnect', '-l'], capture_output=True, text=True)
            output = result.stdout
            
            # Regex to find client ID and name
            # client 28: 'Keystation 49' [type=kernel,card=3]
            client_pattern = re.compile(r"client (\d+): '([^']+)'")
            
            # Find our virtual port ID
            my_client_id = None
            for match in client_pattern.finditer(output):
                client_id, name = match.groups()
                if "HarmonicBeacon" in name: # Logic to find our own port
                    # In python-rtmidi/ALSA, the client name usually matches the python process or similar
                    # But the PORT name we passed is 'HarmonicBeacon Input'
                    # Let's iterate ports to be safe
                    pass

            # Since 'aconnect -l' output structure is hierarchical (client -> ports), 
            # let's parse a bit more robustly or just try to connect by name if possible.
            # actually, aconnect -l shows:
            # client 128: 'HarmonicBeacon Input' [type=user,pid=12345]
            #     0 'HarmonicBeacon Input'
            
            # Let's simple try to find the ID of 'HarmonicBeacon Input'
            # and IDs of potential controllers.
            
            my_port_id = None
            
            # Simple parsing of aconnect -l output line by line
            current_client = None
            
            controllers = []
            
            lines = output.splitlines()
            for line in lines:
                if line.startswith("client "):
                    # New client
                    match = client_pattern.search(line)
                    if match:
                        current_client = match.group(1)
                        client_name = match.group(2)
                        
                        if "HarmonicBeacon Input" in client_name:
                            my_port_id = f"{current_client}:0"
                        elif "Midi Through" in client_name:
                            continue # Skip Midi Through
                        elif "Timer" in client_name or "Announce" in client_name:
                            continue
                        else:
                            # Potential controller
                            # We assume the first port (0) is the output for now
                            controllers.append(f"{current_client}:0")
            
            if my_port_id:
                print(f"[MIDI] Found virtual input at {my_port_id}")
                for ctrl in controllers:
                    print(f"[MIDI] Connecting {ctrl} -> {my_port_id}")
                    subprocess.run(['aconnect', ctrl, my_port_id], capture_output=True)
            else:
                print("[MIDI] Could not determine ID of virtual port, auto-connect failed.")
                
        except Exception as e:
            print(f"[MIDI] Auto-connect failed: {e}")
    
    def close(self) -> None:
        """Close all MIDI input and output ports."""
        for port in self._ports:
            port.close()
        self._ports.clear()
        
        for port in self._output_ports:
            port.close()
        self._output_ports.clear()
        self._port_names.clear()
    
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
