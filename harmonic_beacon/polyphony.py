"""Polyphony tracking for dual-voice management.

Tracks active MIDI notes and their corresponding Beacon and Playable
voice IDs and frequencies for proper Note-On/Note-Off handling.
"""

from dataclasses import dataclass
from typing import Optional

from . import config


@dataclass
class VoicePair:
    """Represents the voices triggered by a single MIDI note."""
    midi_note: int
    velocity: int
    beacon_voice_id: int
    playable_voice_id: int
    # Store frequencies for note-off (Surge XT needs these)
    beacon_frequency: float = 0.0
    playable_frequency: float = 0.0
    # Store original f₁ and harmonic for real-time pitch modulation
    original_f1: float = 54.0
    harmonic_n: int = 1
    # Transposed layer (for borrowed keys with CC29/CC90)
    transposed_voice_id: int = -1  # -1 means not active
    transposed_frequency: float = 0.0
    
    
class VoiceTracker:
    """Tracks active notes and manages voice ID allocation.
    
    Each MIDI note triggers two voices:
    - Beacon voice: The raw harmonic frequency
    - Playable voice: The octave-reduced frequency
    
    This class manages voice IDs and ensures proper cleanup on Note-Off.
    """
    
    def __init__(self, max_voices: int = config.MAX_VOICES):
        """Initialize the voice tracker.
        
        Args:
            max_voices: Maximum number of simultaneous voices
        """
        self.max_voices = max_voices
        
        # Map MIDI note → VoicePair
        self._active_notes: dict[int, VoicePair] = {}
        
        # Voice ID pool (simple incrementing counter)
        self._next_voice_id = 0
        
        # Track last played note for aftertouch center feature
        self._last_played_note: Optional[int] = None
        
    def _allocate_voice_id(self) -> int:
        """Allocate a new voice ID."""
        voice_id = self._next_voice_id
        self._next_voice_id = (self._next_voice_id + 1) % self.max_voices
        return voice_id
    
    def note_on(
        self, 
        midi_note: int, 
        velocity: int,
        beacon_freq: float = 0.0,
        playable_freq: float = 0.0,
        original_f1: float = 54.0,
        harmonic_n: int = 1,
    ) -> tuple[int, int]:
        """Register a new note and allocate voice IDs.
        
        If the note is already active, it will be replaced (retriggered).
        
        Args:
            midi_note: MIDI note number (0-127)
            velocity: Note velocity (1-127)
            beacon_freq: Frequency of the beacon voice in Hz
            playable_freq: Frequency of the playable voice in Hz
            original_f1: The f₁ value when note was triggered (for pitch mod)
            harmonic_n: The harmonic number for this note
            
        Returns:
            Tuple of (beacon_voice_id, playable_voice_id)
        """
        # If note already active, treat as retrigger
        if midi_note in self._active_notes:
            # Return existing IDs (caller should update frequency)
            pair = self._active_notes[midi_note]
            pair.velocity = velocity
            pair.beacon_frequency = beacon_freq
            pair.playable_frequency = playable_freq
            pair.original_f1 = original_f1
            pair.harmonic_n = harmonic_n
            return pair.beacon_voice_id, pair.playable_voice_id
        
        # Allocate new voice IDs
        beacon_id = self._allocate_voice_id()
        playable_id = self._allocate_voice_id()
        
        self._active_notes[midi_note] = VoicePair(
            midi_note=midi_note,
            velocity=velocity,
            beacon_voice_id=beacon_id,
            playable_voice_id=playable_id,
            beacon_frequency=beacon_freq,
            playable_frequency=playable_freq,
            original_f1=original_f1,
            harmonic_n=harmonic_n,
        )
        
        # Track last played note for aftertouch center
        self._last_played_note = midi_note
        
        return beacon_id, playable_id
    
    def note_off(self, midi_note: int) -> Optional[VoicePair]:
        """Release a note and return its voice pair.
        
        Args:
            midi_note: MIDI note number (0-127)
            
        Returns:
            VoicePair if note was active, None otherwise
        """
        return self._active_notes.pop(midi_note, None)
    
    def get_active_notes(self) -> dict[int, VoicePair]:
        """Get all currently active notes.
        
        Returns:
            Dictionary mapping MIDI note → VoicePair
        """
        return self._active_notes.copy()
    
    def get_voice_pair(self, midi_note: int) -> Optional[VoicePair]:
        """Get the voice pair for a specific MIDI note.
        
        Args:
            midi_note: MIDI note number (0-127)
            
        Returns:
            VoicePair if note is active, None otherwise
        """
        return self._active_notes.get(midi_note)
    
    def clear(self) -> list[VoicePair]:
        """Release all active notes.
        
        Returns:
            List of VoicePairs for all notes that were active
        """
        pairs = list(self._active_notes.values())
        self._active_notes.clear()
        return pairs
    
    @property
    def active_count(self) -> int:
        """Number of currently active notes."""
        return len(self._active_notes)
    
    @property
    def voice_count(self) -> int:
        """Number of currently active voices (2 per note)."""
        return len(self._active_notes) * 2
    
    @property
    def last_played_note(self) -> Optional[int]:
        """MIDI note number of the last played note."""
        return self._last_played_note
    
    def get_last_played_pair(self) -> Optional[VoicePair]:
        """Get the VoicePair for the last played note if still active."""
        if self._last_played_note is None:
            return None
        return self._active_notes.get(self._last_played_note)
