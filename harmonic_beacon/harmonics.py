"""Harmonic series calculations and frequency mapping.

This module implements the mathematical core of The Harmonic Beacon,
mapping MIDI notes to the Natural Harmonic Series.
"""

import math

# Harmonic lookup table: MIDI key offset (0-11) → Harmonic number (n)
# Based on the spec's 12-key octave mapping
HARMONIC_MAP: dict[int, int] = {
    0: 1,    # C  → Fundamental (1/1)
    1: 17,   # C# → Minor Second (17/16)
    2: 9,    # D  → Major Second (9/8)
    3: 19,   # Eb → Harmonic minor 3rd (19/16)
    4: 5,    # E  → Major Third (5/4)
    5: 21,   # F  → Narrow Fourth (21/16)
    6: 11,   # F# → Mystic Tritone (11/8)
    7: 3,    # G  → Perfect Fifth (3/2)
    8: 13,   # Ab → Harmonic minor 6th (13/8)
    9: 27,   # A  → Major Sixth (27/16)
    10: 7,   # Bb → Harmonic Seventh (7/4)
    11: 15,  # B  → Major Seventh (15/8)
}

# Interval names for display/debugging
INTERVAL_NAMES: dict[int, str] = {
    0: "Fundamental",
    1: "Minor Second",
    2: "Major Second",
    3: "Harmonic m3",
    4: "Major Third",
    5: "Narrow Fourth",
    6: "Mystic Tritone",
    7: "Perfect Fifth",
    8: "Harmonic m6",
    9: "Major Sixth",
    10: "Harmonic Seventh",
    11: "Major Seventh",
}

# Reference for MIDI note to frequency conversion
MIDI_A4 = 69
FREQ_A4 = 440.0


def get_harmonic_number(midi_note: int) -> int:
    """Map a MIDI note number to its corresponding harmonic number.
    
    Args:
        midi_note: Absolute MIDI note number (0-127)
        
    Returns:
        The harmonic number (n) from the Natural Harmonic Series
    """
    key_offset = midi_note % 12
    return HARMONIC_MAP[key_offset]


def get_octave(midi_note: int) -> int:
    """Get the octave number of a MIDI note.
    
    Args:
        midi_note: Absolute MIDI note number (0-127)
        
    Returns:
        Octave number (C4 = octave 4, following standard MIDI convention)
    """
    return (midi_note // 12) - 1


def beacon_frequency(f1: float, n: int) -> float:
    """Calculate the raw harmonic (Beacon voice) frequency.
    
    The Beacon voice plays the pure harmonic: f₁ × n
    
    Args:
        f1: Base frequency (fundamental) in Hz
        n: Harmonic number
        
    Returns:
        Frequency in Hz
    """
    return f1 * n


def octave_reduce(n: int) -> tuple[float, int]:
    """Reduce a harmonic number to the range [1, 2).
    
    Finds x such that n / 2^x is in [1, 2), giving us the 
    interval ratio within one octave.
    
    Args:
        n: Harmonic number
        
    Returns:
        Tuple of (reduced_ratio, octaves_reduced)
    """
    if n <= 0:
        raise ValueError(f"Harmonic number must be positive, got {n}")
    
    x = 0
    ratio = float(n)
    while ratio >= 2.0:
        ratio /= 2.0
        x += 1
    return ratio, x


def playable_frequency(f1: float, n: int, target_octave: int) -> float:
    """Calculate the octave-reduced (Playable voice) frequency.
    
    The Playable voice transposes the harmonic to the playing octave
    using f₁ × (n / 2^x), then shifts to the target octave.
    
    Args:
        f1: Base frequency (fundamental) in Hz
        n: Harmonic number
        target_octave: Target MIDI octave for the output (4 = C4-B4 range)
        
    Returns:
        Frequency in Hz, transposed to the target octave
    """
    ratio, _ = octave_reduce(n)
    
    # Base frequency in the fundamental's octave
    base_freq = f1 * ratio
    
    # Find what octave the fundamental is in
    f1_midi = frequency_to_midi_float(f1)
    f1_octave = int(f1_midi // 12) - 1
    
    # Shift to target octave
    octave_shift = target_octave - f1_octave
    return base_freq * (2.0 ** octave_shift)


def frequency_to_midi_float(freq: float) -> float:
    """Convert a frequency in Hz to a fractional MIDI note number.
    
    This allows for microtonal precision when sending to synths
    that support it (like Surge XT via OSC).
    
    Args:
        freq: Frequency in Hz
        
    Returns:
        Fractional MIDI note number (e.g., 69.5 = A4 + 50 cents)
    """
    if freq <= 0:
        raise ValueError(f"Frequency must be positive, got {freq}")
    return MIDI_A4 + 12.0 * math.log2(freq / FREQ_A4)


def midi_to_frequency(midi_note: float) -> float:
    """Convert a (fractional) MIDI note number to frequency in Hz.
    
    Args:
        midi_note: MIDI note number (can be fractional for microtones)
        
    Returns:
        Frequency in Hz
    """
    return FREQ_A4 * (2.0 ** ((midi_note - MIDI_A4) / 12.0))


def cents_difference(freq1: float, freq2: float) -> float:
    """Calculate the difference between two frequencies in cents.
    
    Args:
        freq1: First frequency in Hz
        freq2: Second frequency in Hz
        
    Returns:
        Difference in cents (1 cent = 1/100 of a semitone)
    """
    if freq1 <= 0 or freq2 <= 0:
        raise ValueError("Frequencies must be positive")
    return 1200.0 * math.log2(freq2 / freq1)
