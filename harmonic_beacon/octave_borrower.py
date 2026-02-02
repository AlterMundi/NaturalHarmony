"""Octave borrowing fallback for inactive keys.

When a key has no direct harmonic match within tolerance, this module
finds the same interval in a higher octave where it DOES match a harmonic,
and returns that frequency.

Example: D2 has no harmonic match at 25¢ tolerance. But D7 matches n=9.
When pressing D2, we "borrow" from D7 and play 486 Hz (54 * 9).
"""

from dataclasses import dataclass
from typing import Optional

from .key_mapper import KeyMapper, HarmonicMatch


@dataclass
class BorrowedMatch:
    """Result when a key borrows from a higher octave."""
    original_midi: int        # The key that was pressed (e.g., D2 = 38)
    borrowed_midi: int        # The key we borrowed from (e.g., D7 = 98)
    harmonic_n: int           # The harmonic number from the borrowed key
    beacon_frequency: float   # f1 * n (the borrowed frequency)
    octaves_borrowed: int     # How many octaves up we had to look


class OctaveBorrower:
    """Finds harmonic matches by looking in higher octaves.
    
    For keys that don't have a direct harmonic match, this looks for
    the same pitch class (interval) in higher octaves until it finds
    one that matches a harmonic.
    """
    
    def __init__(self, key_mapper: KeyMapper):
        """Initialize with an existing KeyMapper.
        
        Args:
            key_mapper: The KeyMapper with direct harmonic matches
        """
        self.mapper = key_mapper
    
    def borrow(self, midi_note: int) -> Optional[BorrowedMatch]:
        """Find a harmonic by borrowing from a higher octave.
        
        Looks for the same pitch class in successively higher octaves
        until it finds one with a harmonic match.
        
        Args:
            midi_note: The MIDI note that has no direct match
            
        Returns:
            BorrowedMatch if found, None if no match in any octave
        """
        # Don't borrow if the key already has a direct match
        if self.mapper.get_harmonic(midi_note) is not None:
            return None
        
        # Look in higher octaves (each octave is +12 MIDI notes)
        for octaves_up in range(1, 10):  # Up to 9 octaves up
            borrowed_midi = midi_note + (12 * octaves_up)
            
            # Stop if we're past the keyboard range
            if borrowed_midi > self.mapper.highest_midi:
                break
            
            match = self.mapper.get_match(borrowed_midi)
            if match is not None:
                return BorrowedMatch(
                    original_midi=midi_note,
                    borrowed_midi=borrowed_midi,
                    harmonic_n=match.harmonic_n,
                    beacon_frequency=match.beacon_frequency,
                    octaves_borrowed=octaves_up,
                )
        
        return None
    
    def get_frequency(self, midi_note: int) -> Optional[float]:
        """Get frequency for a key, borrowing if needed.
        
        First checks for a direct match, then tries borrowing.
        
        Args:
            midi_note: MIDI note number
            
        Returns:
            Beacon frequency (f1 * n) or None if no match anywhere
        """
        # Try direct match first
        direct = self.mapper.get_beacon_frequency(midi_note)
        if direct is not None:
            return direct
        
        # Try borrowing
        borrowed = self.borrow(midi_note)
        if borrowed is not None:
            return borrowed.beacon_frequency
        
        return None


def build_full_keyboard_map(
    key_mapper: KeyMapper,
    borrower: OctaveBorrower,
) -> dict[int, tuple[int, float, str]]:
    """Build a complete keyboard map showing all notes.
    
    Args:
        key_mapper: The KeyMapper with direct matches
        borrower: The OctaveBorrower for fallbacks
        
    Returns:
        Dict mapping MIDI note -> (harmonic_n, frequency, source)
        where source is 'direct' or 'borrowed:MIDI_XX'
    """
    result = {}
    
    for midi in range(key_mapper.lowest_midi, key_mapper.highest_midi + 1):
        direct = key_mapper.get_match(midi)
        if direct is not None:
            result[midi] = (direct.harmonic_n, direct.beacon_frequency, 'direct')
        else:
            borrowed = borrower.borrow(midi)
            if borrowed is not None:
                result[midi] = (
                    borrowed.harmonic_n,
                    borrowed.beacon_frequency,
                    f'borrowed:MIDI{borrowed.borrowed_midi}'
                )
            else:
                result[midi] = (0, 0.0, 'none')
    
    return result


def dump_full_keyboard(key_mapper: KeyMapper, borrower: OctaveBorrower) -> str:
    """Return a human-readable dump of the full keyboard mapping.
    
    Shows both direct matches and borrowed frequencies.
    """
    lines = [
        f"Full Keyboard Map (f1={key_mapper.f1:.2f}Hz, tol={key_mapper.tolerance_cents}¢)",
        "-" * 70,
    ]
    
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    for midi in range(key_mapper.lowest_midi, key_mapper.highest_midi + 1):
        note = note_names[midi % 12]
        octave = (midi // 12) - 1
        
        direct = key_mapper.get_match(midi)
        if direct is not None:
            sign = '+' if direct.deviation_cents >= 0 else ''
            lines.append(
                f"MIDI {midi:3d} ({note:2s}{octave}) → n={direct.harmonic_n:3d} "
                f"({direct.beacon_frequency:8.2f} Hz) [{sign}{direct.deviation_cents:.1f}¢] DIRECT"
            )
        else:
            borrowed = borrower.borrow(midi)
            if borrowed is not None:
                lines.append(
                    f"MIDI {midi:3d} ({note:2s}{octave}) → n={borrowed.harmonic_n:3d} "
                    f"({borrowed.beacon_frequency:8.2f} Hz) "
                    f"[borrowed from {note}{octave + borrowed.octaves_borrowed}]"
                )
            else:
                lines.append(f"MIDI {midi:3d} ({note:2s}{octave}) → (no match)")
    
    return "\n".join(lines)
