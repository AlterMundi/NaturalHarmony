"""OSC output to Surge XT for microtonal precision.

Sends note and parameter messages to Surge XT via OSC,
allowing for exact frequency control beyond standard MIDI.

Surge XT OSC Spec (v1.3+):
- /fnote frequency velocity [noteID]     - frequency note on
- /fnote/rel frequency velocity [noteID] - frequency note off  
- /allnotesoff                           - release all notes
- All numeric values MUST be sent as floats!
"""

from typing import Optional

try:
    import pyliblo3 as liblo
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
    
    Optionally broadcasts state to a visualizer on a separate port.
    
    Surge XT OSC Note Format (v1.3+):
    - /fnote freq vel [noteID]     → note on at frequency
    - /fnote/rel freq vel [noteID] → note off
    - velocity 0 also releases the note
    """
    
    def __init__(
        self,
        host: str = config.OSC_HOST,
        port: int = config.OSC_PORT,
        broadcast: bool = False,
        broadcast_port: int = config.BROADCAST_PORT,
    ):
        """Initialize the OSC sender.
        
        Args:
            host: Target host address
            port: Target UDP port for Surge XT
            broadcast: Enable broadcasting to visualizer
            broadcast_port: UDP port for visualizer broadcast
        """
        if not HAS_LIBLO:
            raise ImportError(
                "pyliblo3 is required for OSC communication. "
                "Install with: pip install pyliblo3"
            )
        
        self.host = host
        self.port = port
        self.broadcast = broadcast
        self.broadcast_port = broadcast_port
        self._target: Optional[liblo.Address] = None
        self._broadcast_target: Optional[liblo.Address] = None
        
    def open(self) -> None:
        """Open the OSC connection."""
        self._target = liblo.Address(self.host, self.port)
        if self.broadcast:
            self._broadcast_target = liblo.Address(self.host, self.broadcast_port)
        
    def close(self) -> None:
        """Close the OSC connection."""
        self._target = None
        self._broadcast_target = None
        
    def send_note_on(
        self,
        voice_id: int,
        frequency: float,
        velocity: float,
        channel: int = 0,
    ) -> None:
        """Send a note-on message with exact frequency.
        
        Uses Surge XT's /fnote address for frequency-based notes.
        
        Args:
            voice_id: Voice identifier (used as noteID for tracking)
            frequency: Exact frequency in Hz (8.176 - 12543.853)
            velocity: Note velocity (0.0 to 127.0 per Surge spec)
            channel: MIDI channel (unused for /fnote, kept for API compat)
        """
        if self._target is None:
            return
        
        # Surge XT /fnote format: frequency, velocity, [noteID]
        # All values must be floats!
        # Velocity is 0-127 range for Surge (not 0-1)
        vel_scaled = velocity * 127.0 if velocity <= 1.0 else velocity
        
        liblo.send(
            self._target,
            "/fnote",
            ("f", float(frequency)),
            ("f", float(vel_scaled)),
            ("f", float(voice_id)),  # noteID as float
        )
        
    def send_note_off(
        self, 
        voice_id: int, 
        frequency: float = 0.0,
        release_velocity: float = 0.0,
        channel: int = 0,
    ) -> None:
        """Send a note-off message.
        
        Uses Surge XT's /fnote/rel address for note release.
        
        Args:
            voice_id: Voice identifier (noteID) to release
            frequency: Frequency of the note (ignored if noteID provided)
            release_velocity: Release velocity (0.0 to 127.0)
            channel: MIDI channel (unused for /fnote/rel)
        """
        if self._target is None:
            return
        
        # Surge XT /fnote/rel format: frequency, release_velocity, [noteID]
        # When noteID is supplied, frequency is disregarded
        liblo.send(
            self._target,
            "/fnote/rel",
            ("f", float(frequency)),
            ("f", float(release_velocity)),
            ("f", float(voice_id)),  # noteID as float
        )
    
    def send_all_notes_off(self) -> None:
        """Send all-notes-off message to release all sounding notes."""
        if self._target is None:
            return
        liblo.send(self._target, "/allnotesoff")
        
    def send_pitch_expression(
        self,
        voice_id: int,
        semitone_offset: float,
    ) -> None:
        """Send pitch note expression to adjust a sounding note.
        
        Uses Surge XT's /ne/pitch for per-note pitch adjustment.
        This can be used for real-time f₁ modulation.
        
        Args:
            voice_id: noteID of the note to adjust
            semitone_offset: Pitch offset in semitones (-120 to +120)
        """
        if self._target is None:
            return
        
        # /ne/pitch noteID semitone_offset
        liblo.send(
            self._target,
            "/ne/pitch",
            ("f", float(voice_id)),
            ("f", float(semitone_offset)),
        )
        
    def send_parameter(
        self,
        param_path: str,
        value: float,
    ) -> None:
        """Send a parameter change message.
        
        Args:
            param_path: Parameter path (e.g., "a/amp/gain")
            value: Parameter value (0.0 to 1.0 for most params)
        """
        if self._target is None:
            return
        
        address = f"/param/{param_path}"
        liblo.send(self._target, address, ("f", float(value)))
        
    def send_raw(self, address: str, *args) -> None:
        """Send a raw OSC message.
        
        Args:
            address: OSC address pattern
            *args: Message arguments as (type, value) tuples
        """
        if self._target is None:
            return
        liblo.send(self._target, address, *args)
    
    # =========================================================================
    # Broadcast methods for Visualizer
    # =========================================================================
    
    def broadcast_f1(self, hz: float) -> None:
        """Broadcast current f₁ to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(self._broadcast_target, "/beacon/f1", ("f", float(hz)))
    
    def broadcast_anchor(self, midi_note: int) -> None:
        """Broadcast anchor note to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(self._broadcast_target, "/beacon/anchor", ("i", int(midi_note)))
    
    def broadcast_voice_on(self, voice_id: int, freq: float, gain: float, source_note: int) -> None:
        """Broadcast voice activation to visualizer.
        
        Args:
            voice_id: Voice identifier
            freq: Frequency in Hz
            gain: Normalized gain (0-1)
            source_note: MIDI note that triggered this voice
        """
        if self._broadcast_target is None:
            return
        liblo.send(
            self._broadcast_target, 
            "/beacon/voice/on",
            ("i", int(voice_id)),
            ("f", float(freq)),
            ("f", float(gain)),
            ("i", int(source_note)),
        )
    
    def broadcast_voice_off(self, voice_id: int) -> None:
        """Broadcast voice release to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(self._broadcast_target, "/beacon/voice/off", ("i", int(voice_id)))
    
    def broadcast_voice_freq(self, voice_id: int, freq: float) -> None:
        """Broadcast frequency update (LFO sweep) to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(
            self._broadcast_target,
            "/beacon/voice/freq",
            ("i", int(voice_id)),
            ("f", float(freq)),
        )
    
    def broadcast_key_on(self, note: int, velocity: int) -> None:
        """Broadcast key press to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(
            self._broadcast_target,
            "/beacon/key/on",
            ("i", int(note)),
            ("i", int(velocity)),
        )
    
    def broadcast_key_off(self, note: int) -> None:
        """Broadcast key release to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(self._broadcast_target, "/beacon/key/off", ("i", int(note)))
    
    def broadcast_cc(self, cc_num: int, value: int) -> None:
        """Broadcast CC change to visualizer."""
        if self._broadcast_target is None:
            return
        liblo.send(
            self._broadcast_target,
            "/beacon/cc",
            ("i", int(cc_num)),
            ("i", int(value)),
        )
    
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
        vel_scaled = velocity * 127.0 if velocity <= 1.0 else velocity
        msg = {
            "type": "note_on",
            "address": "/fnote",
            "voice_id": voice_id,
            "frequency": frequency,
            "velocity": vel_scaled,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] /fnote {frequency:.2f} {vel_scaled:.0f} {voice_id}")
            
    def send_note_off(
        self, 
        voice_id: int, 
        frequency: float = 0.0,
        release_velocity: float = 0.0,
        channel: int = 0,
    ) -> None:
        """Log note-off message."""
        msg = {
            "type": "note_off",
            "address": "/fnote/rel",
            "voice_id": voice_id,
            "frequency": frequency,
            "release_velocity": release_velocity,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] /fnote/rel {frequency:.2f} {release_velocity:.0f} {voice_id}")
    
    def send_all_notes_off(self) -> None:
        """Log all-notes-off message."""
        msg = {"type": "all_notes_off", "address": "/allnotesoff"}
        self._message_log.append(msg)
        if self.verbose:
            print("[MockOSC] /allnotesoff")
            
    def send_pitch_expression(
        self,
        voice_id: int,
        semitone_offset: float,
    ) -> None:
        """Log pitch expression message."""
        msg = {
            "type": "pitch_expression",
            "address": "/ne/pitch",
            "voice_id": voice_id,
            "semitone_offset": semitone_offset,
        }
        self._message_log.append(msg)
        if self.verbose:
            print(f"[MockOSC] /ne/pitch {voice_id} {semitone_offset:.2f}")
            
    def get_log(self) -> list[dict]:
        """Get the message log."""
        return self._message_log.copy()
    
    def clear_log(self) -> None:
        """Clear the message log."""
        self._message_log.clear()
    
    # Broadcast stubs (no-op in mock mode)
    def broadcast_f1(self, hz: float) -> None:
        pass
    
    def broadcast_anchor(self, midi_note: int) -> None:
        pass
    
    def broadcast_voice_on(self, voice_id: int, freq: float, gain: float, source_note: int) -> None:
        pass
    
    def broadcast_voice_off(self, voice_id: int) -> None:
        pass
    
    def broadcast_voice_freq(self, voice_id: int, freq: float) -> None:
        pass
    
    def broadcast_key_on(self, note: int, velocity: int) -> None:
        pass
    
    def broadcast_key_off(self, note: int) -> None:
        pass
    
    def broadcast_cc(self, cc_num: int, value: int) -> None:
        pass
