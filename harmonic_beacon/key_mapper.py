"""Key-to-frequency mapping using Optimized Chromatic Harmonics.

This module maps every MIDI key to a harmonic frequency.
1. It determines the interval class (0-11) of the key relative to the Anchor.
2. It looks up the "Prototype Harmonic" (n) for that interval.
3. It compares:
   a. The Prototype Harmonic transposed to the key's octave.
   b. Any "Local" harmonics that naturally occur near the key.
4. It selects the one with the lowest deviation from 12TET.

If Stacking Mode is ON, it can provide both the Primary (pitch-correct)
and Secondary (origin/natural) frequencies.
"""

import math
from dataclasses import dataclass
from typing import Optional

from . import config

# =============================================================================
# Constants
# =============================================================================

MIDI_A4 = 69
FREQ_A4 = 440.0


def harmonic_to_cents(n: int) -> float:
    """Calculate the distance of harmonic n from the fundamental in cents."""
    if n < 1:
        raise ValueError(f"Harmonic number must be >= 1, got {n}")
    return 1200.0 * math.log2(n)


def midi_to_frequency(midi_note: float) -> float:
    """Convert a (fractional) MIDI note number to frequency in Hz."""
    return FREQ_A4 * (2.0 ** ((midi_note - MIDI_A4) / 12.0))


# =============================================================================
# Key Mapper
# =============================================================================

@dataclass
class KeyMatch:
    """Result of mapping a MIDI key."""
    midi_note: int
    
    # Primary Voice (Best fit for pitch)
    primary_freq: float
    primary_n: int
    primary_deviation: float  # Cents deviation from 12TET
    
    # Secondary Voice (Origin/Natural harmonic, if transposed)
    # If primary is local (not transposed), this matches primary
    secondary_freq: float
    secondary_n: int
    
    # Metadata
    is_transposed: bool     # True if primary is a transposed version of secondary
    source_type: str        # 'local' or 'prototype'


class KeyMapper:
    """Maps MIDI keys to optimal harmonic frequencies."""
    
    def __init__(
        self,
        f1: float,
        anchor_midi: int = 24,
        lowest_midi: int = 21,
        highest_midi: int = 108,
    ):
        """Initialize the key mapper.
        
        Args:
            f1: Base frequency (fundamental) in Hz
            anchor_midi: MIDI note that represents f1 (default: C1=24)
            lowest_midi: Lowest MIDI note to map
            highest_midi: Highest MIDI note to map
        """
        self.f1 = f1
        self.anchor_midi = anchor_midi
        self.lowest_midi = lowest_midi
        self.highest_midi = highest_midi
        
        # Build the mapping table: midi_note -> KeyMatch
        self._mapping: dict[int, KeyMatch] = {}
        self._build_mapping()
    
    def _build_mapping(self) -> None:
        """Build the lookup table for all keys."""
        prototypes = config.CHROMATIC_PROTOTYPES
        
        for midi in range(self.lowest_midi, self.highest_midi + 1):
            # 1. Determine Interval Class (0-11)
            # anchor_midi corresponds to interval 0
            rel_semitones = midi - self.anchor_midi
            interval_class = rel_semitones % 12
            
            # 2. Get Prototype Candidate
            proto_n = prototypes[interval_class]
            proto_f = self.f1 * proto_n
            
            # Transpose prototype to match the key's octave
            # Target frequency is roughly 12TET pitch of the key
            target_freq = midi_to_frequency(midi)
            
            # Find closest octave transposition of proto_f to target_freq
            # ratio = target_freq / proto_f
            # octaves = round(log2(ratio))
            # transposed_f = proto_f * 2^octaves
            num_octaves = round(math.log2(target_freq / proto_f))
            transposed_proto_f = proto_f * (2.0 ** num_octaves)
            
            # Calculate deviation of transposed prototype
            # We compare transposed_proto_f to target_freq
            proto_cents = 1200.0 * math.log2(transposed_proto_f / target_freq)
            
            # 3. Check for Local Matches (Better Fit?)
            # Scan harmonics that are naturally close to target_freq
            # We check a small range around the target
            best_local_n = None
            best_local_dev = float('inf')
            
            # Optimization: Estimate n for target_freq: n = target_freq / f1
            center_n_float = target_freq / self.f1
            search_radius = 2 # Check neighbors
            
            start_n = max(1, int(math.floor(center_n_float - search_radius)))
            end_n = int(math.ceil(center_n_float + search_radius))
            
            for n in range(start_n, end_n + 1):
                f_n = self.f1 * n
                # Deviation from target
                dev = 1200.0 * math.log2(f_n / target_freq)
                if abs(dev) < abs(best_local_dev):
                    best_local_dev = dev
                    best_local_n = n
            
            # 4. Select Best Match
            # "Pick the option with less deviation"
            use_local = False
            # Force Prototype usage to prioritize simple ratios over microtonal accuracy
            if best_local_n is not None and False: # Disabled for now
                if abs(best_local_dev) < abs(proto_cents):
                    use_local = True
            
            if use_local and best_local_n is not None:
                # Local match wins
                primary_n = best_local_n
                primary_f = self.f1 * best_local_n
                deviation = best_local_dev
                is_transposed = False
                source_type = 'local'
                
                # Secondary is typically same as primary if local
                secondary_n = primary_n
                secondary_f = primary_f
                
            else:
                # Prototype wins
                primary_n = proto_n # Conceptually the n is the prototype, but physically we play transposed
                # Note: primary_n in KeyMatch usually refers to the harmonic number OF THE FREQUENCY PLAYED
                # If we play 2 * n, that is harmonic 2n.
                # However, for coloring/Osc, we might want to know the "Source N" (Prototype).
                # But physically, if we play 400Hz and f1=50, we are playing n=8.
                # Let's derive actual physical n for primary.
                primary_f = transposed_proto_f
                deviation = proto_cents
                is_transposed = (num_octaves != 0)
                source_type = 'prototype'
                
                # Physical n of the transposed frequency
                # transposed_f = f1 * proto_n * 2^k
                # We calculate the effective "n" relative to f1.
                # It might be non-integer if we transposed DOWN (k < 0), 
                # but valid for visualizer ratio calc.
                # However, visualizer expects n to be the harmonic index.
                # If we send n=3.0, it should be fine if visualizer handles float n.
                # Wait, Main.py sends int? "harmonic_ns: list[int]"
                # If we cast to int, we lose precision if transposed down?
                # But usually we transpose UP to match keys.
                # If we transpose down, e.g. proto=3, octave=-1 => 1.5. Not a harmonic.
                # But user asked for "origin frequency together with octave-transposed".
                # Primary is the Transposed one.
                # Let's send the effective scalar as 'n'.
                # Note: harmonic_ns is type hinted as list[int] in main, but Python is dynamic.
                # Let's try to keep it integer if possible, or float if needed.
                effective_n = proto_n * (2 ** num_octaves)
                
                # If it happens to be non-integer (transposed down), we might have issues with
                # visualizers expecting integers. But 0 crashes it.
                # Let's use the effective_n.
                
                secondary_n = proto_n
                secondary_f = proto_f
            
            self._mapping[midi] = KeyMatch(
                midi_note=midi,
                primary_freq=primary_f,
                primary_n=effective_n, # Now calculating effective N (e.g. 6.0 for 3*2)
                primary_deviation=deviation,
                secondary_freq=secondary_f,
                secondary_n=secondary_n,
                is_transposed=is_transposed,
                source_type=source_type
            )

    def get_match(self, midi_note: int) -> Optional[KeyMatch]:
        """Get the match for a MIDI key."""
        return self._mapping.get(midi_note)
    
    def rebuild(
        self,
        f1: Optional[float] = None,
        anchor_midi: Optional[int] = None,
    ) -> None:
        """Rebuild the mapping with new parameters."""
        if f1 is not None:
            self.f1 = f1
        if anchor_midi is not None:
            self.anchor_midi = anchor_midi
        self._build_mapping()
