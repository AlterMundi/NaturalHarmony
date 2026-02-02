"""Tests for the KeyMapper module.

Verifies that MIDI keys map correctly to natural harmonics with symmetric
tolerance matching.

Natural Harmonic Series (anchor at C1 = MIDI 24):
    n  | Cents    | Semitones | Interval        | Nearest Key | Error
    ---|----------|-----------|-----------------|-------------|-------
    1  | 0        | 0.00      | Fundamental     | C1  (24)    | 0¢
    2  | 1200     | 12.00     | Octave          | C2  (36)    | 0¢
    3  | 1901.96  | 19.02     | Oct + Fifth     | G2  (43)    | -2¢
    4  | 2400     | 24.00     | 2 Octaves       | C3  (48)    | 0¢
    5  | 2786.31  | 27.86     | 2 Oct + Maj 3rd | E3  (52)    | +14¢
    6  | 3101.96  | 31.02     | 2 Oct + Fifth   | G3  (55)    | -2¢
    7  | 3368.83  | 33.69     | 2 Oct + min 7th | Bb3 (58)    | +31¢
    8  | 3600     | 36.00     | 3 Octaves       | C4  (60)    | 0¢
"""

import math
import pytest
import sys
sys.path.insert(0, '/home/nicolas/OS_projects/NaturalHarmony')

from harmonic_beacon.key_mapper import (
    KeyMapper,
    harmonic_to_cents,
    create_default_mapper,
)


# =============================================================================
# Test harmonic_to_cents matches known values
# =============================================================================

class TestHarmonicToCents:
    """Verify harmonic_to_cents returns correct values."""
    
    def test_n1_is_zero(self):
        assert harmonic_to_cents(1) == 0.0
    
    def test_n2_is_octave(self):
        assert harmonic_to_cents(2) == 1200.0
    
    def test_n3_is_fifth_plus_octave(self):
        # 1200 * log2(3) ≈ 1901.96 cents
        cents = harmonic_to_cents(3)
        assert abs(cents - 1901.96) < 0.01
    
    def test_n4_is_two_octaves(self):
        assert harmonic_to_cents(4) == 2400.0
    
    def test_n5_is_third_plus_two_octaves(self):
        # 1200 * log2(5) ≈ 2786.31 cents
        cents = harmonic_to_cents(5)
        assert abs(cents - 2786.31) < 0.01
    
    def test_n6_is_fifth_plus_two_octaves(self):
        # 1200 * log2(6) ≈ 3101.96 cents
        cents = harmonic_to_cents(6)
        assert abs(cents - 3101.96) < 0.01
    
    def test_n7_is_harmonic_seventh(self):
        # 1200 * log2(7) ≈ 3368.83 cents
        cents = harmonic_to_cents(7)
        assert abs(cents - 3368.83) < 0.01
    
    def test_n8_is_three_octaves(self):
        assert harmonic_to_cents(8) == 3600.0


# =============================================================================
# Test KeyMapper matches expected musical intervals
# =============================================================================

class TestHarmonicSeriesMapping:
    """Test that keys map to the correct harmonics (the real musical intervals)."""
    
    @pytest.fixture
    def mapper(self):
        # Anchor at C1 (MIDI 24), 25 cent tolerance (covers most harmonics)
        return KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=25.0)
    
    # --- Exact octaves (0 cents error) ---
    
    def test_c1_is_fundamental(self, mapper):
        """C1 (MIDI 24, anchor) = n=1 (fundamental)"""
        assert mapper.get_harmonic(24) == 1
    
    def test_c2_is_octave(self, mapper):
        """C2 (MIDI 36) = n=2 (octave)"""
        assert mapper.get_harmonic(36) == 2
    
    def test_c3_is_two_octaves(self, mapper):
        """C3 (MIDI 48) = n=4 (two octaves)"""
        assert mapper.get_harmonic(48) == 4
    
    def test_c4_is_three_octaves(self, mapper):
        """C4 (MIDI 60) = n=8 (three octaves)"""
        assert mapper.get_harmonic(60) == 8
    
    # --- Fifths (2 cents error) ---
    
    def test_g2_is_fifth_plus_octave(self, mapper):
        """G2 (MIDI 43) = n=3 (fifth + octave, only 2¢ off!)"""
        assert mapper.get_harmonic(43) == 3
    
    def test_g3_is_fifth_plus_two_octaves(self, mapper):
        """G3 (MIDI 55) = n=6 (fifth + two octaves, only 2¢ off!)"""
        assert mapper.get_harmonic(55) == 6
    
    # --- Major third (14 cents error) ---
    
    def test_e3_is_major_third(self, mapper):
        """E3 (MIDI 52) = n=5 (major 3rd + two octaves, 14¢ off)"""
        assert mapper.get_harmonic(52) == 5
    
    # --- Harmonic seventh (31 cents error - may not match at 25¢ tolerance) ---
    
    def test_bb3_harmonic_seventh_needs_wider_tolerance(self, mapper):
        """Bb3 (MIDI 58) = n=7 (harmonic 7th, 31¢ off - outside 25¢!)"""
        # At 25¢ tolerance, this should NOT match
        assert mapper.get_harmonic(58) is None
    
    def test_bb3_matches_with_wider_tolerance(self):
        """Bb3 (MIDI 58) = n=7 with 35¢ tolerance"""
        mapper = KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=35.0)
        assert mapper.get_harmonic(58) == 7


class TestSymmetricTolerance:
    """Test that tolerance works symmetrically (above AND below)."""
    
    def test_g2_is_slightly_below_n3_and_still_matches(self):
        """G2 (1900 cents) is 2 cents BELOW n=3 (1901.96 cents).
        With symmetric tolerance, this should match!
        """
        mapper = KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=5.0)
        # G2 = MIDI 43 = 19 semitones = 1900 cents
        # n=3 = 1901.96 cents
        # Error = -1.96 cents (below)
        assert mapper.get_harmonic(43) == 3
    
    def test_e3_is_slightly_above_n5_and_still_matches(self):
        """E3 (2800 cents) is 14 cents ABOVE n=5 (2786.31 cents).
        With tolerance >= 14, this should match.
        """
        mapper = KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=15.0)
        assert mapper.get_harmonic(52) == 5


class TestNoMatchBehavior:
    """Test keys between harmonics with tight tolerance."""
    
    @pytest.fixture
    def tight_mapper(self):
        return KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=1.0)
    
    def test_between_n1_and_n2_no_match(self, tight_mapper):
        """Keys between C1 and C2 should not match at 1¢ tolerance."""
        for midi in range(25, 36):  # C#1 to B1
            assert tight_mapper.get_harmonic(midi) is None, f"MIDI {midi} should not match"
    
    def test_octaves_still_match_tight(self, tight_mapper):
        """Exact octaves should still match at tight tolerance."""
        assert tight_mapper.get_harmonic(24) == 1  # C1
        assert tight_mapper.get_harmonic(36) == 2  # C2
        assert tight_mapper.get_harmonic(48) == 4  # C3
        assert tight_mapper.get_harmonic(60) == 8  # C4


# =============================================================================
# Test beacon frequency calculation
# =============================================================================

class TestBeaconFrequency:
    """Test beacon frequency (f1 * n) calculation."""
    
    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=54.0, anchor_midi=24, tolerance_cents=25.0)
    
    def test_fundamental_frequency(self, mapper):
        """C1 → f1 = 54 Hz"""
        assert mapper.get_beacon_frequency(24) == 54.0
    
    def test_octave_frequency(self, mapper):
        """C2 → 2 * f1 = 108 Hz"""
        assert mapper.get_beacon_frequency(36) == 108.0
    
    def test_fifth_frequency(self, mapper):
        """G2 → 3 * f1 = 162 Hz"""
        assert mapper.get_beacon_frequency(43) == 162.0
    
    def test_two_octaves_frequency(self, mapper):
        """C3 → 4 * f1 = 216 Hz"""
        assert mapper.get_beacon_frequency(48) == 216.0
    
    def test_major_third_frequency(self, mapper):
        """E3 → 5 * f1 = 270 Hz"""
        assert mapper.get_beacon_frequency(52) == 270.0


# =============================================================================
# Visual dump for manual verification
# =============================================================================

class TestKeyboardDump:
    """Print full keyboard mapping for visual verification."""
    
    def test_dump_25_cent_tolerance(self):
        """Print mapping at 25¢ tolerance (default)."""
        mapper = KeyMapper(
            f1=54.0,
            anchor_midi=24,
            tolerance_cents=25.0,
            lowest_midi=24,
            highest_midi=72,
        )
        print("\n" + "=" * 60)
        print("25¢ TOLERANCE - Should match most natural harmonics:")
        print("=" * 60)
        print(mapper.dump_mapping())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
