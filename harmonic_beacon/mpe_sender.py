"""MPE (MIDI Polyphonic Expression) output for microtonal control.

Sends MPE messages to a virtual MIDI port, allowing any MPE-compatible
synthesizer to receive microtonal harmonic frequencies.

MPE Protocol:
- Channel 1: Master channel (global messages like sustain pedal)
- Channels 2-16: Member channels (one per voice, 15 max polyphony)
- Per-channel pitch bend for microtonal tuning (±48 semitones range)
"""

import math
from typing import Optional

try:
    import mido
    from mido import Message
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False
    mido = None  # type: ignore
    Message = None  # type: ignore

from . import config
from .harmonics import frequency_to_midi_float, FREQ_A4, MIDI_A4


# =============================================================================
# MPE Constants
# =============================================================================

# MPE uses channels 2-16 for member channels (15 voices max)
# Channel 1 is the master channel
MPE_MASTER_CHANNEL = 0  # 0-indexed (MIDI channel 1)
MPE_MEMBER_CHANNELS = list(range(1, 16))  # 0-indexed (MIDI channels 2-16)
MPE_MAX_VOICES = len(MPE_MEMBER_CHANNELS)  # 15 voices

# Pitch bend range in semitones (standard MPE uses ±48)
MPE_PITCH_BEND_RANGE = 48

# Virtual MIDI port name
MPE_PORT_NAME = "Harmonic Beacon MPE"


def _frequency_to_note_and_bend(frequency: float) -> tuple[int, int]:
    """Convert a frequency to MIDI note + pitch bend value.
    
    Args:
        frequency: Target frequency in Hz
        
    Returns:
        Tuple of (midi_note, pitch_bend_value)
        - midi_note: Nearest MIDI note number (0-127)
        - pitch_bend_value: 14-bit pitch bend (0-16383, center=8192)
    """
    # Calculate fractional MIDI note
    midi_float = frequency_to_midi_float(frequency)
    
    # Round to nearest integer note
    midi_note = round(midi_float)
    midi_note = max(0, min(127, midi_note))
    
    # Calculate semitone offset from the integer note
    semitone_offset = midi_float - midi_note
    
    # Convert to pitch bend value
    # Range: -MPE_PITCH_BEND_RANGE to +MPE_PITCH_BEND_RANGE semitones
    # Value: 0 to 16383, center at 8192
    normalized_bend = semitone_offset / MPE_PITCH_BEND_RANGE
    normalized_bend = max(-1.0, min(1.0, normalized_bend))
    
    # Convert to 14-bit value (0-16383)
    pitch_bend = int(8192 + normalized_bend * 8191)
    pitch_bend = max(0, min(16383, pitch_bend))
    
    return midi_note, pitch_bend


class MpeSender:
    """Sends MPE messages to a virtual MIDI port.
    
    Manages voice allocation across MPE member channels and
    provides microtonal pitch control via per-channel pitch bend.
    """
    
    def __init__(
        self,
        port_name: str = MPE_PORT_NAME,
        pitch_bend_range: int = MPE_PITCH_BEND_RANGE,
        verbose: bool = False,
    ):
        """Initialize the MPE sender.
        
        Args:
            port_name: Name of the virtual MIDI port to create
            pitch_bend_range: Pitch bend range in semitones (default: 48)
            verbose: Print debug messages
        """
        if not HAS_MIDO:
            raise ImportError(
                "mido is required for MPE output. "
                "Install with: pip install mido python-rtmidi"
            )
        
        self.port_name = port_name
        self.pitch_bend_range = pitch_bend_range
        self.verbose = verbose
        
        self._port: Optional[mido.ports.BaseOutput] = None
        
        # Voice allocation: voice_id -> channel (0-indexed)
        self._voice_channels: dict[int, int] = {}
        
        # Channel pool: available member channels
        self._available_channels: list[int] = list(MPE_MEMBER_CHANNELS)
        
        # Track active notes per channel for cleanup
        self._channel_notes: dict[int, int] = {}  # channel -> midi_note
        
    def open(self) -> str:
        """Open the virtual MIDI port.
        
        Returns:
            Name of the opened port
            
        Raises:
            RuntimeError: If port cannot be opened
        """
        try:
            # Try to open a virtual output port
            self._port = mido.open_output(self.port_name, virtual=True)
            
            if self.verbose:
                print(f"✓ MPE: Virtual port '{self.port_name}' created")
            
            # Send MPE configuration (RPN for pitch bend range)
            self._configure_mpe()
            
            return self.port_name
            
        except Exception as e:
            # Fall back to listing available ports
            available = mido.get_output_names()
            raise RuntimeError(
                f"Could not create virtual MIDI port: {e}\n"
                f"Available outputs: {available}\n"
                "Make sure python-rtmidi is installed: pip install python-rtmidi"
            )
    
    def _configure_mpe(self) -> None:
        """Send MPE configuration messages.
        
        Configures pitch bend range on all member channels.
        """
        if self._port is None:
            return
        
        for channel in MPE_MEMBER_CHANNELS:
            # RPN for pitch bend sensitivity
            # CC 101 = RPN MSB (0 for pitch bend range)
            # CC 100 = RPN LSB (0 for pitch bend range)
            # CC 6 = Data Entry MSB (semitones)
            # CC 38 = Data Entry LSB (cents)
            self._port.send(Message('control_change', channel=channel, control=101, value=0))
            self._port.send(Message('control_change', channel=channel, control=100, value=0))
            self._port.send(Message('control_change', channel=channel, control=6, value=self.pitch_bend_range))
            self._port.send(Message('control_change', channel=channel, control=38, value=0))
            # Reset RPN
            self._port.send(Message('control_change', channel=channel, control=101, value=127))
            self._port.send(Message('control_change', channel=channel, control=100, value=127))
    
    def close(self) -> None:
        """Close the virtual MIDI port."""
        if self._port is not None:
            # Send all notes off on all channels
            self.send_all_notes_off()
            self._port.close()
            self._port = None
            
            if self.verbose:
                print("✓ MPE: Port closed")
    
    def _allocate_channel(self, voice_id: int) -> Optional[int]:
        """Allocate a member channel for a voice.
        
        Args:
            voice_id: Voice identifier
            
        Returns:
            Allocated channel (0-indexed) or None if no channels available
        """
        # If voice already has a channel, return it
        if voice_id in self._voice_channels:
            return self._voice_channels[voice_id]
        
        # Allocate from pool
        if self._available_channels:
            channel = self._available_channels.pop(0)
            self._voice_channels[voice_id] = channel
            return channel
        
        # No channels available - voice stealing would go here
        if self.verbose:
            print(f"⚠ MPE: No channels available for voice {voice_id}")
        return None
    
    def _release_channel(self, voice_id: int) -> Optional[int]:
        """Release a channel back to the pool.
        
        Args:
            voice_id: Voice identifier
            
        Returns:
            Released channel or None if voice wasn't allocated
        """
        channel = self._voice_channels.pop(voice_id, None)
        if channel is not None:
            self._available_channels.append(channel)
            self._channel_notes.pop(channel, None)
        return channel
    
    def send_note_on(
        self,
        voice_id: int,
        frequency: float,
        velocity: float,
    ) -> None:
        """Send a note-on message with exact frequency.
        
        Args:
            voice_id: Voice identifier
            frequency: Target frequency in Hz
            velocity: Normalized velocity (0.0 to 1.0)
        """
        if self._port is None:
            return
        
        # Allocate channel
        channel = self._allocate_channel(voice_id)
        if channel is None:
            return
        
        # Convert frequency to note + pitch bend
        midi_note, pitch_bend = _frequency_to_note_and_bend(frequency)
        
        # Convert velocity to 0-127
        velocity_int = max(1, min(127, int(velocity * 127)))
        
        # Send pitch bend first (before note on)
        self._port.send(Message('pitchwheel', channel=channel, pitch=pitch_bend - 8192))
        
        # Send note on
        self._port.send(Message('note_on', channel=channel, note=midi_note, velocity=velocity_int))
        
        # Track the note on this channel
        self._channel_notes[channel] = midi_note
        
        if self.verbose:
            print(f"🎹 MPE Note ON: ch={channel+1} note={midi_note} freq={frequency:.2f}Hz bend={pitch_bend}")
    
    def send_note_off(
        self,
        voice_id: int,
        frequency: float = 0.0,
        release_velocity: float = 0.0,
    ) -> None:
        """Send a note-off message.
        
        Args:
            voice_id: Voice identifier
            frequency: Original frequency (used to recalculate note if needed)
            release_velocity: Normalized release velocity (0.0 to 1.0)
        """
        if self._port is None:
            return
        
        channel = self._voice_channels.get(voice_id)
        if channel is None:
            return
        
        # Get the original MIDI note for this channel
        midi_note = self._channel_notes.get(channel)
        if midi_note is None:
            # Fallback: calculate from frequency
            if frequency > 0:
                midi_note, _ = _frequency_to_note_and_bend(frequency)
            else:
                midi_note = 60  # Default to middle C
        
        # Convert release velocity
        release_vel_int = max(0, min(127, int(release_velocity * 127)))
        
        # Send note off
        self._port.send(Message('note_off', channel=channel, note=midi_note, velocity=release_vel_int))
        
        # Release channel back to pool
        self._release_channel(voice_id)
        
        if self.verbose:
            print(f"🎹 MPE Note OFF: ch={channel+1} note={midi_note}")
    
    def send_pitch_expression(
        self,
        voice_id: int,
        semitone_offset: float,
    ) -> None:
        """Send pitch bend to adjust a sounding note.
        
        Args:
            voice_id: Voice identifier
            semitone_offset: Pitch offset in semitones
        """
        if self._port is None:
            return
        
        channel = self._voice_channels.get(voice_id)
        if channel is None:
            return
        
        # Convert to pitch bend value
        normalized_bend = semitone_offset / self.pitch_bend_range
        normalized_bend = max(-1.0, min(1.0, normalized_bend))
        
        pitch_bend = int(8192 + normalized_bend * 8191)
        pitch_bend = max(0, min(16383, pitch_bend))
        
        self._port.send(Message('pitchwheel', channel=channel, pitch=pitch_bend - 8192))
    
    def send_all_notes_off(self) -> None:
        """Send all-notes-off on all channels."""
        if self._port is None:
            return
        
        # Send all notes off on master and all member channels
        for channel in [MPE_MASTER_CHANNEL] + MPE_MEMBER_CHANNELS:
            self._port.send(Message('control_change', channel=channel, control=123, value=0))
        
        # Clear tracking
        self._voice_channels.clear()
        self._channel_notes.clear()
        self._available_channels = list(MPE_MEMBER_CHANNELS)
    
    @property
    def is_open(self) -> bool:
        """Whether the port is open."""
        return self._port is not None
    
    @property
    def active_voices(self) -> int:
        """Number of currently active voices."""
        return len(self._voice_channels)
    
    @property
    def available_channels(self) -> int:
        """Number of available member channels."""
        return len(self._available_channels)
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class MockMpeSender:
    """Mock MPE sender for testing without actual MIDI output."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._is_open = False
        
    def open(self) -> str:
        self._is_open = True
        if self.verbose:
            print("✓ MPE (mock): Ready")
        return "Mock MPE Port"
    
    def close(self) -> None:
        self._is_open = False
        if self.verbose:
            print("✓ MPE (mock): Closed")
    
    def send_note_on(self, voice_id: int, frequency: float, velocity: float) -> None:
        if self.verbose:
            print(f"🎹 MPE (mock) Note ON: voice={voice_id} freq={frequency:.2f}Hz vel={velocity:.2f}")
    
    def send_note_off(self, voice_id: int, frequency: float = 0.0, release_velocity: float = 0.0) -> None:
        if self.verbose:
            print(f"🎹 MPE (mock) Note OFF: voice={voice_id}")
    
    def send_pitch_expression(self, voice_id: int, semitone_offset: float) -> None:
        pass
    
    def send_all_notes_off(self) -> None:
        if self.verbose:
            print("🎹 MPE (mock): All notes off")
    
    @property
    def is_open(self) -> bool:
        return self._is_open
    
    @property
    def active_voices(self) -> int:
        return 0
    
    @property
    def available_channels(self) -> int:
        return 15
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
