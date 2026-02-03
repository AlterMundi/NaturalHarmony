"""Polyphony tracking for multi-voice management.

Tracks active MIDI notes and their corresponding voice IDs
and frequencies for proper Note-On/Note-Off handling.
"""

from dataclasses import dataclass, field
from typing import Optional

from . import config


@dataclass
class VoicePair:
    """Represents the voices triggered by a single MIDI note.
    
    Can hold multiple voices if Multi-Harmonic mode is active.
    """
    midi_note: int
    velocity: int
    
    # List of allocated voice IDs and their properties
    voice_ids: list[int] = field(default_factory=list)
    frequencies: list[float] = field(default_factory=list)
    harmonic_ns: list[int] = field(default_factory=list)
    
    # Store original f₁ for real-time pitch modulation
    original_f1: float = 54.0
    
    # Transposed layer (for borrowed keys)
    transposed_voice_id: int = -1
    transposed_frequency: float = 0.0
    
    @property
    def beacon_voice_id(self) -> int:
        """Get primary voice ID (first voice, for legacy compatibility)."""
        return self.voice_ids[0] if self.voice_ids else -1
    
    @property
    def beacon_frequency(self) -> float:
        """Get primary frequency (first voice)."""
        return self.frequencies[0] if self.frequencies else 0.0
        
    @property
    def harmonic_n(self) -> int:
        """Get primary harmonic number (first voice)."""
        return self.harmonic_ns[0] if self.harmonic_ns else 1


class VoiceTracker:
    """Tracks active notes and manages voice ID allocation.
    
    Supports allocating multiple harmonic voices per MIDI note.
    """
    
    def __init__(self, max_voices: int = config.MAX_VOICES):
        """Initialize the voice tracker."""
        self.max_voices = max_voices
        self._active_notes: dict[int, VoicePair] = {}
        self._next_voice_id = 0
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
        frequencies: list[float],
        harmonic_ns: list[int],
        original_f1: float = 54.0,
    ) -> list[int]:
        """Register a new note and allocate voice IDs.
        
        Args:
            midi_note: MIDI note number (0-127)
            velocity: Note velocity (1-127)
            frequencies: List of frequencies to play
            harmonic_ns: List of harmonic numbers
            original_f1: The f₁ value when note was triggered
            
        Returns:
            List of allocated voice IDs
        """
        if not frequencies:
            return []
        
        # Allocate voice IDs
        voice_ids = [self._allocate_voice_id() for _ in frequencies]
        
        # Create VoicePair
        pair = VoicePair(
            midi_note=midi_note,
            velocity=velocity,
            voice_ids=voice_ids,
            frequencies=list(frequencies),
            harmonic_ns=list(harmonic_ns),
            original_f1=original_f1,
        )
        
        self._active_notes[midi_note] = pair
        self._last_played_note = midi_note
        
        return voice_ids
    
    def note_off(self, midi_note: int) -> Optional[VoicePair]:
        """Release a note and return its voice pair."""
        return self._active_notes.pop(midi_note, None)
    
    def get_active_notes(self) -> dict[int, VoicePair]:
        """Get all currently active notes."""
        return self._active_notes.copy()
    
    def get_voice_pair(self, midi_note: int) -> Optional[VoicePair]:
        """Get the voice pair for a specific MIDI note."""
        return self._active_notes.get(midi_note)
    
    def clear(self) -> list[VoicePair]:
        """Release all active notes."""
        pairs = list(self._active_notes.values())
        self._active_notes.clear()
        return pairs
    
    @property
    def active_count(self) -> int:
        """Number of currently active notes."""
        return len(self._active_notes)
    
    @property
    def voice_count(self) -> int:
        """Number of currently active voices."""
        count = 0
        for pair in self._active_notes.values():
            count += len(pair.voice_ids)
            if pair.transposed_voice_id >= 0:
                count += 1
        return count
    
    @property
    def last_played_note(self) -> Optional[int]:
        """MIDI note number of the last played note."""
        return self._last_played_note
    
    def get_last_played_pair(self) -> Optional[VoicePair]:
        """Get the VoicePair for the last played note if still active."""
        if self._last_played_note is None:
            return None
        return self._active_notes.get(self._last_played_note)
