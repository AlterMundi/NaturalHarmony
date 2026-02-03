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

# Maximum harmonic frequency (hearing limit)
MAX_HARMONIC_FREQ = 20000.0


def get_harmonic_number(midi_note: int) -> int:
    """Map a MIDI note number to its corresponding harmonic number (12-key mode).
    
    DEPRECATED: Use get_harmonic_for_key() for full 88-key support.
    
    Args:
        midi_note: Absolute MIDI note number (0-127)
        
    Returns:
        The harmonic number (n) from the fixed 12-interval table
    """
    key_offset = midi_note % 12
    return HARMONIC_MAP[key_offset]


def get_harmonic_for_key(
    midi_note: int, 
    anchor_note: int = 24,
    cents_threshold: float = 25.0,
) -> int:
    """Calculate the harmonic for any key position (88-key hybrid mode).
    
    Uses a two-tier approach:
    1. If the key lands close to a pure harmonic (within cents_threshold),
       use that harmonic directly.
    2. Otherwise, fall back to the 12-interval table for the key's
       chromatic position.
    
    Args:
        midi_note: MIDI note number (0-127)
        anchor_note: MIDI note that represents f₁ (default: 24 = C1)
        cents_threshold: Maximum cents deviation to count as "exact" (default: 25)
        
    Returns:
        Harmonic number (n ≥ 1)
        
    Examples:
        >>> get_harmonic_for_key(36, anchor=24)  # C2 lands exactly on n=2
        2
        >>> get_harmonic_for_key(59, anchor=24)  # B3 doesn't land exactly, uses table
        15
    """
    semitones = midi_note - anchor_note
    
    # Calculate the exact harmonic position
    n_exact = 2 ** (semitones / 12)
    # Use floor (int) instead of round() for left-aligned mapping
    n_nearest = max(1, int(n_exact))
    
    # Calculate cents deviation from the nearest harmonic
    if n_nearest > 0:
        perfect_semitones = 12 * math.log2(n_nearest)
        cents_error = abs(semitones - perfect_semitones) * 100
    else:
        cents_error = float('inf')
    
    # If close to a pure harmonic, use it directly
    if cents_error <= cents_threshold:
        return n_nearest
    
    # Otherwise, fall back to the 12-interval table
    # This preserves the musical character of each chromatic position
    return HARMONIC_MAP[midi_note % 12]


def get_harmonic_info(
    midi_note: int, 
    anchor_note: int = 24,
    cents_threshold: float = 25.0,
) -> dict:
    """Get detailed harmonic information for a key.
    
    Args:
        midi_note: MIDI note number (0-127)
        anchor_note: MIDI note that represents f₁
        cents_threshold: Threshold for "exact" harmonic landing
        
    Returns:
        Dictionary with harmonic details including whether it's a direct
        harmonic landing or an interval fallback.
    """
    semitones = midi_note - anchor_note
    # Calculate the exact harmonic position
    n_exact = 2 ** (semitones / 12)
    # Use floor (int) instead of round() for left-aligned mapping
    n_nearest = max(1, int(n_exact))
    
    # Calculate cents deviation from the nearest harmonic
    if n_nearest > 0:
        perfect_semitones = 12 * math.log2(n_nearest)
        cents_error = (semitones - perfect_semitones) * 100
    else:
        cents_error = 0.0
    
    is_direct = abs(cents_error) <= cents_threshold
    
    if is_direct:
        n_used = n_nearest
        source = "direct"
    else:
        # For fallback, we also want to align to the floor of the interval
        # But HARMONIC_MAP is 12-tone, so this stays as chromatic lookup
        # The key logic change is mainly for the "direct" hit detection above
        n_used = HARMONIC_MAP[midi_note % 12]
        source = "interval"
    
    return {
        "midi_note": midi_note,
        "harmonic": n_used,
        "n_exact": n_exact,
        "n_nearest": n_nearest,
        "cents_error": cents_error,
        "semitones_from_anchor": semitones,
        "source": source,  # "direct" or "interval"
    }


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


def get_standard_frequency(midi_note: int) -> float:
    """Get the standard frequency for a MIDI note (A4=440Hz ET).
    
    Args:
        midi_note: MIDI note number
        
    Returns:
        Frequency in Hz
    """
    return FREQ_A4 * (2.0 ** ((midi_note - MIDI_A4) / 12.0))


def playable_frequency(f1: float, n: int, target_note: int) -> float:
    """Calculate the adaptive playable frequency.
    
    Ensures the voice plays in the octave expected for the pressed key,
    regardless of the raw harmonic frequency.
    
    Args:
        f1: Base frequency (fundamental) in Hz
        n: Harmonic number
        target_note: The MIDI note that was pressed (defines the target pitch)
        
    Returns:
        Frequency in Hz, transposed to match the target key's octave
    """
    # 1. Calculate the raw harmonic frequency (The Beacon Voice)
    raw_freq = beacon_frequency(f1, n)
    
    # 2. Calculate the standard expectation for this key (A4=440Hz)
    target_freq = get_standard_frequency(target_note)
    
    # 3. Handle edge case for silence
    if raw_freq <= 0 or target_freq <= 0:
        return 0.0
        
    # 4. Calculate how many octaves we are away from the target
    # ratio = target / raw
    # octaves = log2(ratio)
    ratio = target_freq / raw_freq
    octave_shift = round(math.log2(ratio))
    
    # 5. Apply the shift
    return raw_freq * (2.0 ** octave_shift)


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


# =============================================================================
# Tolerance-Based Harmonic Search
# =============================================================================

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


def find_harmonics_for_key(
    semitones_from_anchor: int,
    tolerance_cents: float,
    max_harmonic: int = 128,
) -> list[int]:
    """Find all harmonics within tolerance of a key position.
    
    Args:
        semitones_from_anchor: Semitone distance from anchor key (can be negative)
        tolerance_cents: Maximum deviation in cents to count as a match
        max_harmonic: Highest harmonic to search
        
    Returns:
        List of matching harmonic numbers, sorted ascending. Empty if none.
        
    Examples:
        >>> find_harmonics_for_key(12, 10.0)  # Octave above anchor
        [2]
        >>> find_harmonics_for_key(19, 5.0)   # ~Perfect 5th + octave
        [3]
        >>> find_harmonics_for_key(48, 50.0)  # High C - multiple matches
        [16]
    """
    key_cents = semitones_from_anchor * 100.0
    matches = []
    
    for n in range(1, max_harmonic + 1):
        harmonic_cents = harmonic_to_cents(n)
        deviation = abs(harmonic_cents - key_cents)
        if deviation <= tolerance_cents:
            matches.append(n)
    
    return matches


def find_harmonics_with_fallback(
    midi_note: int,
    anchor_note: int,
    tolerance_cents: float,
    max_harmonic: int = 128,
) -> list[int]:
    """Find harmonics for a key, with neighbor fallback if none found.
    
    If no harmonics are within tolerance, searches outward from the key
    until a neighbor is found that has at least one match.
    
    Args:
        midi_note: MIDI note number (0-127)
        anchor_note: MIDI note that represents f₁
        tolerance_cents: Maximum deviation in cents
        max_harmonic: Highest harmonic to search
        
    Returns:
        List of matching harmonic numbers (never empty)
    """
    semitones = midi_note - anchor_note
    
    # Try exact position first
    matches = find_harmonics_for_key(semitones, tolerance_cents, max_harmonic)
    if matches:
        return matches
    
    # Search outward from the key position
    for offset in range(1, 128):
        # Try below
        matches_below = find_harmonics_for_key(
            semitones - offset, tolerance_cents, max_harmonic
        )
        if matches_below:
            return matches_below
        
        # Try above
        matches_above = find_harmonics_for_key(
            semitones + offset, tolerance_cents, max_harmonic
        )
        if matches_above:
            return matches_above
    
    # Absolute fallback: fundamental
    return [1]

