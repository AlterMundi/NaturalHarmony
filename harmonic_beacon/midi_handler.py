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
        self._port: Optional[mido.ports.BaseInput] = None
        self._output_port: Optional[mido.ports.BaseOutput] = None
        self._port_name: Optional[str] = None
        
    def open(self) -> str:
        """Open the MIDI input port.
        
        Returns:
            Name of the opened port
            
        Raises:
            RuntimeError: If no suitable port is found
        """
        available_ports = mido.get_input_names()
        
        if not available_ports:
            raise RuntimeError("No MIDI input ports available")
        
        # Find matching port
        port_name = None
        if self.port_pattern:
            for name in available_ports:
                if self.port_pattern.lower() in name.lower():
                    port_name = name
                    break
        
        # Fall back to first port if no match
        if port_name is None:
            port_name = available_ports[0]
            if self.port_pattern:
                print(f"Warning: No port matching '{self.port_pattern}' found, "
                      f"using '{port_name}'")
        
        self._port = mido.open_input(port_name)
        self._port_name = port_name
        
        # Try to open output port with same name for feedback
        try:
            output_ports = mido.get_output_names()
            # Try exact match first
            if port_name in output_ports:
                self._output_port = mido.open_output(port_name)
                if self.debug:
                    print(f"[MIDI] Opened output port: {port_name}")
            else:
                 # Try approximate match
                 for out_name in output_ports:
                     if port_name[:-2] in out_name: # Simple heuristic
                         self._output_port = mido.open_output(out_name)
                         if self.debug:
                             print(f"[MIDI] Opened output port (approx): {out_name}")
                         break
        except Exception as e:
            if self.debug:
                print(f"[MIDI] Could not open output port: {e}")
                
        return port_name
    
    def close(self) -> None:
        """Close the MIDI input port."""
        if self._port is not None:
            self._port.close()
            self._port = None
        if self._output_port is not None:
            self._output_port.close()
            self._output_port = None
            self._port_name = None
    
    def poll(self) -> list[mido.Message]:
        """Poll for pending MIDI messages (non-blocking).
        
        Returns:
            List of pending MIDI messages
        """
        if self._port is None:
            return []
        
        messages = list(self._port.iter_pending())
        
        if self.debug:
            for msg in messages:
                print(f"[MIDI IN] {msg}")
                
        return messages

    def send_message(self, msg: mido.Message) -> None:
        """Send a MIDI message to the output port."""
        if self._output_port:
            try:
                self._output_port.send(msg)
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
    
    def is_tolerance_control(self, msg: mido.Message) -> bool:
        """Check if a message is the tolerance CC (CC67)."""
        return msg.type == "control_change" and msg.control == config.TOLERANCE_CC
    
    def is_lfo_rate_control(self, msg: mido.Message) -> bool:
        """Check if a message is the LFO rate CC (CC68)."""
        return msg.type == "control_change" and msg.control == config.LFO_RATE_CC
    
    def is_vibrato_mode_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the vibrato mode toggle CC (CC23)."""
        return msg.type == "control_change" and msg.control == config.VIBRATO_MODE_CC
    
    def is_multi_harmonic_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the multi-harmonic toggle CC (CC29)."""
        return msg.type == "control_change" and msg.control == config.MULTI_HARMONIC_CC
    
    def is_max_harmonics_control(self, msg: mido.Message) -> bool:
        """Check if a message is the max harmonics CC (CC90)."""
        return msg.type == "control_change" and msg.control == config.MAX_HARMONICS_CC
    
    def is_primary_lock_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the primary voice lock CC (CC28)."""
        return msg.type == "control_change" and msg.control == config.PRIMARY_LOCK_CC
    
    def is_harmonic_mix_control(self, msg: mido.Message) -> bool:
        """Check if a message is the harmonic mix CC (CC89)."""
        return msg.type == "control_change" and msg.control == config.HARMONIC_MIX_CC
    
    def is_natural_harmonics_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the Natural Harmonics toggle (CC30)."""
        return msg.type == "control_change" and msg.control == config.NATURAL_HARMONICS_CC
    
    def is_natural_level_control(self, msg: mido.Message) -> bool:
        """Check if a message is the Natural Harmonics Level control (CC92)."""
        return msg.type == "control_change" and msg.control == config.NATURAL_LEVEL_CC

    def is_panic_cc(self, msg: mido.Message) -> bool:
        """Check if a message is the Panic button CC (e.g. 111)."""
        return msg.type == "control_change" and msg.control == config.PANIC_NOTE
    
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
        """Name of the currently open port."""
        return self._port_name
    
    @property
    def is_open(self) -> bool:
        """Whether the port is currently open."""
        return self._port is not None
    
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
