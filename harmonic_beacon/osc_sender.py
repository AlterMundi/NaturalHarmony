"""OSC output to Surge XT for microtonal precision.

Sends note and parameter messages to Surge XT via OSC,
allowing for exact frequency control beyond standard MIDI.
"""

from typing import Optional

try:
    import liblo
    HAS_LIBLO = True
except ImportError:
    HAS_LIBLO = False
    liblo = None  # type: ignore

from . import config
from .harmonics import frequency_to_midi_float


class OscSender:
    """Sends OSC messages to Surge XT.
    
    Uses pyliblo to communicate with Surge XT's OSC interface,
    enabling microtonal note control with exact frequencies.
    """
    
    def __init__(
        self,
        host: str = config.OSC_HOST,
        port: int = config.OSC_PORT,
    ):
        """Initialize the OSC sender.
        
        Args:
            host: Target host address
            port: Target UDP port
        """
        if not HAS_LIBLO:
            raise ImportError(
                "pyliblo3 is required for OSC communication. "
                "Install with: pip install pyliblo3"
            )
        
        self.host = host
        self.port = port
        self._target: Optional[liblo.Address] = None
        
    def open(self) -> None:
        """Open the OSC connection."""
        self._target = liblo.Address(self.host, self.port)
        
    def close(self) -> None:
        """Close the OSC connection."""
        self._target = None
        
    def send_note_on(
        self,
        voice_id: int,
        frequency: float,
        velocity: float,
        channel: int = 0,
    ) -> None:
        """Send a note-on message with exact frequency.
        
        Args:
            voice_id: Voice identifier for tracking
            frequency: Exact frequency in Hz
            velocity: Note velocity (0.0 to 1.0)
            channel: MIDI channel (0-15)
        """
        if self._target is None:
            return
        
        # Convert frequency to fractional MIDI note for Surge
        midi_note = frequency_to_midi_float(frequency)
        
        # Send OSC message
        # Format: /surge/noteon voice_id midi_note velocity channel
        liblo.send(
            self._target,
            config.OSC_NOTE_ON,
            ("i", voice_id),      # Voice ID
            ("f", midi_note),     # Fractional MIDI note
            ("f", velocity),      # Velocity (0-1)
            ("i", channel),       # Channel
        )
        
    def send_note_off(self, voice_id: int, channel: int = 0) -> None:
        """Send a note-off message.
        
        Args:
            voice_id: Voice identifier to release
            channel: MIDI channel (0-15)
        """
        if self._target is None:
            return
        
        # Send OSC message
        # Format: /surge/noteoff voice_id channel
        liblo.send(
            self._target,
            config.OSC_NOTE_OFF,
            ("i", voice_id),
            ("i", channel),
        )
        
    def send_frequency_update(
        self,
        voice_id: int,
        frequency: float,
        channel: int = 0,
    ) -> None:
        """Update the frequency of an active voice.
        
        Used for real-time f₁ modulation of sounding notes.
        
        Args:
            voice_id: Voice identifier to update
            frequency: New frequency in Hz
            channel: MIDI channel (0-15)
        """
        if self._target is None:
            return
        
        midi_note = frequency_to_midi_float(frequency)
        
        # Send pitch update
        # This uses a custom address pattern for frequency updates
        liblo.send(
            self._target,
            "/surge/voice/pitch",
            ("i", voice_id),
            ("f", midi_note),
            ("i", channel),
        )
        
    def send_parameter(
        self,
        param_path: str,
        value: float,
    ) -> None:
        """Send a parameter change message.
        
        Args:
            param_path: Parameter path (e.g., "osc/1/pitch")
            value: Parameter value
        """
        if self._target is None:
            return
        
        address = f"{config.OSC_PARAMETER}/{param_path}"
        liblo.send(self._target, address, ("f", value))
        
    def send_raw(self, address: str, *args) -> None:
        """Send a raw OSC message.
        
        Args:
            address: OSC address pattern
            *args: Message arguments as (type, value) tuples
        """
        if self._target is None:
            return
        liblo.send(self._target, address, *args)
    
    @property
    def is_open(self) -> bool:
        """Whether the OSC connection is open."""
        return self._target is not None
    
    def __enter__(self) -> "OscSender":
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


class MockOscSender(OscSender):
    """Mock OSC sender for testing without Surge XT.
    
    Logs all messages to stdout instead of sending via OSC.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize without requiring liblo."""
        self.host = kwargs.get("host", config.OSC_HOST)
        self.port = kwargs.get("port", config.OSC_PORT)
        self._target = None
        self.verbose = kwargs.get("verbose", True)
        self._message_log: list[dict] = []
        
    def open(self) -> None:
        """Mock open."""
        self._target = "mock"
        if self.verbose:
            print(f"[MockOSC] Opened connection to {self.host}:{self.port}")
            
    def close(self) -> None:
        """Mock close."""
        self._target = None
        if self.verbose:
            print("[MockOSC] Connection closed")
            
    def send_note_on(
        self,
        voice_id: int,
        frequency: float,
        velocity: float,
        channel: int = 0,
    ) -> None:
        """Log note-on message."""
        midi_note = frequency_to_midi_float(frequency)
        msg = {
            "type": "note_on",
            "voice_id": voice_id,
            "frequency": frequency,
            "midi_note": midi_note,
            "velocity": velocity,
            "channel": channel,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] Note ON: voice={voice_id}, "
                  f"freq={frequency:.2f}Hz (MIDI {midi_note:.2f}), "
                  f"vel={velocity:.2f}")
            
    def send_note_off(self, voice_id: int, channel: int = 0) -> None:
        """Log note-off message."""
        msg = {
            "type": "note_off",
            "voice_id": voice_id,
            "channel": channel,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] Note OFF: voice={voice_id}")
            
    def send_frequency_update(
        self,
        voice_id: int,
        frequency: float,
        channel: int = 0,
    ) -> None:
        """Log frequency update message."""
        midi_note = frequency_to_midi_float(frequency)
        msg = {
            "type": "freq_update",
            "voice_id": voice_id,
            "frequency": frequency,
            "midi_note": midi_note,
            "channel": channel,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] Freq Update: voice={voice_id}, "
                  f"freq={frequency:.2f}Hz (MIDI {midi_note:.2f})")
            
    def get_log(self) -> list[dict]:
        """Get the message log."""
        return self._message_log.copy()
    
    def clear_log(self) -> None:
        """Clear the message log."""
        self._message_log.clear()
