"""Key-to-frequency mapping for natural harmonics.

This module maps MIDI keys to natural harmonic frequencies based on tolerance.
A key matches a harmonic if it's within tolerance_cents of that harmonic's
exact position (symmetric matching - above OR below).
"""

import math
from dataclasses import dataclass
from typing import Optional

# =============================================================================
# Constants
# =============================================================================

MIDI_A4 = 69
FREQ_A4 = 440.0


# =============================================================================
# Natural Harmonic Series Reference
# =============================================================================
# 
# The harmonic series with anchor at C1 (MIDI 24):
#
# n  | Cents    | Semitones | Interval        | Nearest Key | Error
# ---|----------|-----------|-----------------|-------------|-------
# 1  | 0        | 0.00      | Fundamental     | C1  (24)    | 0¢
# 2  | 1200     | 12.00     | Octave          | C2  (36)    | 0¢
# 3  | 1901.96  | 19.02     | Oct + Fifth     | G2  (43)    | -2¢
# 4  | 2400     | 24.00     | 2 Octaves       | C3  (48)    | 0¢
# 5  | 2786.31  | 27.86     | 2 Oct + Maj 3rd | E3  (52)    | +14¢
# 6  | 3101.96  | 31.02     | 2 Oct + Fifth   | G3  (55)    | -2¢
# 7  | 3368.83  | 33.69     | 2 Oct + min 7th | Bb3 (58)    | +31¢
# 8  | 3600     | 36.00     | 3 Octaves       | C4  (60)    | 0¢
#


def harmonic_to_cents(n: int) -> float:
    """Calculate the distance of harmonic n from the fundamental in cents.
    
    Args:
        n: Harmonic number (n >= 1)
        
    Returns:
        Cents above the fundamental (1200 cents = 1 octave)
    """
    if n < 1:
        raise ValueError(f"Harmonic number must be >= 1, got {n}")
    return 1200.0 * math.log2(n)


def midi_to_frequency(midi_note: float) -> float:
    """Convert a (fractional) MIDI note number to frequency in Hz."""
    return FREQ_A4 * (2.0 ** ((midi_note - MIDI_A4) / 12.0))


def frequency_to_midi(freq: float) -> float:
    """Convert frequency in Hz to fractional MIDI note number."""
    if freq <= 0:
        raise ValueError(f"Frequency must be positive, got {freq}")
    return MIDI_A4 + 12.0 * math.log2(freq / FREQ_A4)


# =============================================================================
# Key Mapper
# =============================================================================

@dataclass
class HarmonicMatch:
    """Result of mapping a MIDI key to a harmonic."""
    midi_note: int
    harmonic_n: int
    beacon_frequency: float  # f1 * n
    deviation_cents: float   # How far from exact (can be negative)


class KeyMapper:
    """Maps MIDI keys to natural harmonic frequencies.
    
    Uses symmetric tolerance matching: a key matches a harmonic if
    |key_cents - harmonic_cents| <= tolerance_cents.
    
    Stores ALL harmonics that match a key within tolerance.
    """
    
    def __init__(
        self,
        f1: float,
        anchor_midi: int = 24,
        tolerance_cents: float = 25.0,
        max_harmonic: int = 128,
        lowest_midi: int = 21,
        highest_midi: int = 108,
    ):
        """Initialize the key mapper.
        
        Args:
            f1: Base frequency (fundamental) in Hz
            anchor_midi: MIDI note that represents f1 (default: C1=24)
            tolerance_cents: Maximum deviation in cents to match (default: 25)
            max_harmonic: Highest harmonic to consider (default: 128)
            lowest_midi: Lowest MIDI note to map (default: A0=21)
            highest_midi: Highest MIDI note to map (default: C8=108)
        """
        self.f1 = f1
        self.anchor_midi = anchor_midi
        self.tolerance_cents = tolerance_cents
        self.max_harmonic = max_harmonic
        self.lowest_midi = lowest_midi
        self.highest_midi = highest_midi
        
        # Build the mapping table: midi_note -> list of (harmonic_n, deviation) or None
        self._mapping: dict[int, list[tuple[int, float]] | None] = {}
        self._build_mapping()
    
    def _build_mapping(self) -> None:
        """Build the MIDI-to-harmonic lookup table.
        
        For each MIDI key, find ALL harmonics within tolerance.
        Matches are stored sorted by harmonic number (n).
        Skips harmonics exceeding 20kHz.
        """
        # Maximum frequency for harmonics (hearing limit)
        MAX_FREQ_HZ = 20000.0
        
        for midi in range(self.lowest_midi, self.highest_midi + 1):
            key_cents = (midi - self.anchor_midi) * 100.0
            
            matches: list[tuple[int, float]] = []
            
            # Search through harmonics to find matches
            for n in range(1, self.max_harmonic + 1):
                # Skip harmonics that would exceed 20kHz
                if self.f1 * n > MAX_FREQ_HZ:
                    break
                
                h_cents = harmonic_to_cents(n)
                deviation = key_cents - h_cents  # Can be positive or negative
                abs_deviation = abs(deviation)
                
                # Collect matches within tolerance
                if abs_deviation <= self.tolerance_cents:
                    matches.append((n, deviation))
                
                # Optimization: if harmonic is way past the key, stop searching
                # (Assuming tolerance_cents << 100, checking slightly beyond ensures we don't miss edge cases)
                if h_cents > key_cents + self.tolerance_cents + 1.0:
                    break
            
            if matches:
                self._mapping[midi] = matches
            else:
                self._mapping[midi] = None
    
    def get_harmonic(self, midi_note: int) -> Optional[int]:
        """Get the harmonic number for a MIDI key (lowest match).
        
        Returns:
            Harmonic number if key matches, None otherwise
        """
        matches = self._mapping.get(midi_note)
        if not matches:
            return None
        return matches[0][0]  # Return n of the first/lowest match
    
    def get_match(self, midi_note: int) -> Optional[HarmonicMatch]:
        """Get full match information for a MIDI key (lowest match)."""
        matches = self._mapping.get(midi_note)
        if matches is None:
            return None
        
        n, deviation = matches[0]  # Use first match
        return HarmonicMatch(
            midi_note=midi_note,
            harmonic_n=n,
            beacon_frequency=self.f1 * n,
            deviation_cents=deviation,
        )
    
    def get_all_matches(self, midi_note: int) -> list[HarmonicMatch]:
        """Get all matching harmonics for a MIDI key.
        
        Returns:
            List of HarmonicMatch objects, sorted by harmonic number.
        """
        matches_data = self._mapping.get(midi_note)
        if matches_data is None:
            return []
        
        return [
            HarmonicMatch(
                midi_note=midi_note,
                harmonic_n=n,
                beacon_frequency=self.f1 * n,
                deviation_cents=deviation,
            )
            for n, deviation in matches_data
        ]
    
    def get_beacon_frequency(self, midi_note: int) -> Optional[float]:
        """Get the beacon frequency (f1 * n) for a MIDI key (lowest match)."""
        matches = self._mapping.get(midi_note)
        if not matches:
            return None
        return self.f1 * matches[0][0]
    
    def rebuild(
        self,
        f1: Optional[float] = None,
        anchor_midi: Optional[int] = None,
        tolerance_cents: Optional[float] = None,
    ) -> None:
        """Rebuild the mapping with new parameters."""
        if f1 is not None:
            self.f1 = f1
        if anchor_midi is not None:
            self.anchor_midi = anchor_midi
        if tolerance_cents is not None:
            self.tolerance_cents = tolerance_cents
        self._build_mapping()
    
    def dump_mapping(self) -> str:
        """Return a human-readable dump of the full mapping."""
        lines = [
            f"KeyMapper: f1={self.f1:.2f}Hz, anchor=MIDI{self.anchor_midi}, "
            f"tolerance={self.tolerance_cents}¢",
            f"Range: MIDI {self.lowest_midi} to {self.highest_midi}",
            "-" * 60,
        ]
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        for midi in range(self.lowest_midi, self.highest_midi + 1):
            note = note_names[midi % 12]
            octave = (midi // 12) - 1
            matches = self._mapping.get(midi)
            
            if matches:
                # Format first match
                n, dev = matches[0]
                freq = self.f1 * n
                sign = '+' if dev >= 0 else ''
                match_str = f"n={n:3d} ({freq:8.2f} Hz) [{sign}{dev:.1f}¢]"
                
                # Mention others
                if len(matches) > 1:
                    match_str += f" (+{len(matches)-1} others: "
                    match_str += ", ".join([f"n={m[0]}" for m in matches[1:]])
                    match_str += ")"
                
                lines.append(f"MIDI {midi:3d} ({note:2s}{octave}) → {match_str}")
            else:
                lines.append(f"MIDI {midi:3d} ({note:2s}{octave}) → (no match)")
        
        return "\n".join(lines)


def create_default_mapper(
    f1: float = 54.0,
    anchor_midi: int = 24,
    tolerance_cents: float = 25.0,
) -> KeyMapper:
    """Create a KeyMapper with default settings."""
    return KeyMapper(
        f1=f1,
        anchor_midi=anchor_midi,
        tolerance_cents=tolerance_cents,
    )
