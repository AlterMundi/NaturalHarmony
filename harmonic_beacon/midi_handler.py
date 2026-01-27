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
    ):
        """Initialize the MIDI handler.
        
        Args:
            port_pattern: Substring to match in port names, or None for first port
            f1_cc: CC number used for f₁ modulation
        """
        self.port_pattern = port_pattern
        self.f1_cc = f1_cc
        self._port: Optional[mido.ports.BaseInput] = None
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
        return port_name
    
    def close(self) -> None:
        """Close the MIDI input port."""
        if self._port is not None:
            self._port.close()
            self._port = None
            self._port_name = None
    
    def poll(self) -> list[mido.Message]:
        """Poll for pending MIDI messages (non-blocking).
        
        Returns:
            List of pending MIDI messages
        """
        if self._port is None:
            return []
        return list(self._port.iter_pending())
    
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
    
    def is_aftertouch(self, msg: mido.Message) -> bool:
        """Check if a message is channel aftertouch."""
        return msg.type == "aftertouch"
    
    def is_mode_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the aftertouch mode toggle CC (CC22)."""
        return msg.type == "control_change" and msg.control == config.AFTERTOUCH_MODE_CC
    
    def is_tolerance_control(self, msg: mido.Message) -> bool:
        """Check if a message is the tolerance CC (CC67)."""
        return msg.type == "control_change" and msg.control == config.TOLERANCE_CC
    
    def is_lfo_rate_control(self, msg: mido.Message) -> bool:
        """Check if a message is the LFO rate CC (CC68)."""
        return msg.type == "control_change" and msg.control == config.LFO_RATE_CC
    
    def is_vibrato_mode_toggle(self, msg: mido.Message) -> bool:
        """Check if a message is the vibrato mode toggle CC (CC23)."""
        return msg.type == "control_change" and msg.control == config.VIBRATO_MODE_CC
    
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
