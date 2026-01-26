"""Unit tests for harmonics module."""

import math
import pytest

from harmonic_beacon.harmonics import (
    HARMONIC_MAP,
    get_harmonic_number,
    get_octave,
    beacon_frequency,
    octave_reduce,
    playable_frequency,
    frequency_to_midi_float,
    midi_to_frequency,
    cents_difference,
)


class TestHarmonicMap:
    """Tests for the harmonic mapping table."""
    
    def test_all_12_keys_mapped(self):
        """Verify all 12 chromatic keys have mappings."""
        for i in range(12):
            assert i in HARMONIC_MAP
            
    def test_fundamental_is_1(self):
        """C (0) maps to harmonic 1 (fundamental)."""
        assert HARMONIC_MAP[0] == 1
        
    def test_perfect_fifth_is_3(self):
        """G (7) maps to harmonic 3 (perfect fifth)."""
        assert HARMONIC_MAP[7] == 3
        
    def test_major_third_is_5(self):
        """E (4) maps to harmonic 5 (major third)."""
        assert HARMONIC_MAP[4] == 5
        
    def test_harmonic_seventh_is_7(self):
        """Bb (10) maps to harmonic 7 (harmonic seventh)."""
        assert HARMONIC_MAP[10] == 7


class TestGetHarmonicNumber:
    """Tests for get_harmonic_number function."""
    
    def test_c4_returns_1(self):
        """C4 (MIDI 60) returns harmonic 1."""
        assert get_harmonic_number(60) == 1
        
    def test_g4_returns_3(self):
        """G4 (MIDI 67) returns harmonic 3."""
        assert get_harmonic_number(67) == 3
        
    def test_octave_equivalence(self):
        """Same pitch class in different octaves returns same harmonic."""
        assert get_harmonic_number(48) == get_harmonic_number(60) == get_harmonic_number(72)
        
    def test_all_chromatic_notes(self):
        """All notes in an octave map correctly."""
        for offset in range(12):
            midi_note = 60 + offset  # C4 through B4
            expected = HARMONIC_MAP[offset]
            assert get_harmonic_number(midi_note) == expected


class TestGetOctave:
    """Tests for get_octave function."""
    
    def test_c4_is_octave_4(self):
        """C4 (MIDI 60) is in octave 4."""
        assert get_octave(60) == 4
        
    def test_c3_is_octave_3(self):
        """C3 (MIDI 48) is in octave 3."""
        assert get_octave(48) == 3
        
    def test_a4_is_octave_4(self):
        """A4 (MIDI 69) is in octave 4."""
        assert get_octave(69) == 4


class TestBeaconFrequency:
    """Tests for beacon_frequency function."""
    
    def test_fundamental(self):
        """n=1 returns the base frequency."""
        assert beacon_frequency(54.0, 1) == 54.0
        
    def test_first_harmonic(self):
        """n=2 returns double the base frequency."""
        assert beacon_frequency(54.0, 2) == 108.0
        
    def test_third_harmonic(self):
        """n=3 returns triple the base frequency."""
        assert beacon_frequency(54.0, 3) == 162.0
        
    def test_with_different_f1(self):
        """Works with different base frequencies."""
        assert beacon_frequency(100.0, 5) == 500.0


class TestOctaveReduce:
    """Tests for octave_reduce function."""
    
    def test_1_stays_1(self):
        """n=1 reduces to 1.0, 0 octaves."""
        ratio, x = octave_reduce(1)
        assert ratio == 1.0
        assert x == 0
        
    def test_2_reduces_to_1(self):
        """n=2 reduces to 1.0, 1 octave."""
        ratio, x = octave_reduce(2)
        assert ratio == 1.0
        assert x == 1
        
    def test_3_reduces_to_1_5(self):
        """n=3 reduces to 1.5 (perfect fifth)."""
        ratio, x = octave_reduce(3)
        assert ratio == 1.5
        assert x == 1
        
    def test_5_reduces_to_1_25(self):
        """n=5 reduces to 1.25 (major third)."""
        ratio, x = octave_reduce(5)
        assert ratio == 1.25
        assert x == 2
        
    def test_7_reduces_to_1_75(self):
        """n=7 reduces to 1.75 (harmonic seventh)."""
        ratio, x = octave_reduce(7)
        assert ratio == 1.75
        assert x == 2
        
    def test_invalid_raises(self):
        """Non-positive harmonics raise ValueError."""
        with pytest.raises(ValueError):
            octave_reduce(0)
        with pytest.raises(ValueError):
            octave_reduce(-1)


class TestFrequencyConversion:
    """Tests for frequency/MIDI conversion functions."""
    
    def test_a4_is_69(self):
        """A4 (440 Hz) converts to MIDI 69."""
        assert frequency_to_midi_float(440.0) == pytest.approx(69.0)
        
    def test_a3_is_57(self):
        """A3 (220 Hz) converts to MIDI 57."""
        assert frequency_to_midi_float(220.0) == pytest.approx(57.0)
        
    def test_round_trip(self):
        """Converting to MIDI and back yields original frequency."""
        original = 432.0
        midi = frequency_to_midi_float(original)
        recovered = midi_to_frequency(midi)
        assert recovered == pytest.approx(original)
        
    def test_midi_69_is_440(self):
        """MIDI 69 converts to 440 Hz."""
        assert midi_to_frequency(69) == pytest.approx(440.0)
        
    def test_fractional_midi(self):
        """Fractional MIDI notes work correctly."""
        # MIDI 69.5 should be 50 cents above A4
        freq = midi_to_frequency(69.5)
        cents = cents_difference(440.0, freq)
        assert cents == pytest.approx(50.0)
        
    def test_invalid_frequency_raises(self):
        """Non-positive frequencies raise ValueError."""
        with pytest.raises(ValueError):
            frequency_to_midi_float(0)
        with pytest.raises(ValueError):
            frequency_to_midi_float(-100)


class TestCentsDifference:
    """Tests for cents_difference function."""
    
    def test_octave_is_1200_cents(self):
        """An octave is 1200 cents."""
        assert cents_difference(220.0, 440.0) == pytest.approx(1200.0)
        
    def test_equal_is_zero(self):
        """Equal frequencies are 0 cents apart."""
        assert cents_difference(440.0, 440.0) == pytest.approx(0.0)
        
    def test_semitone_is_100_cents(self):
        """A semitone is approximately 100 cents."""
        # A4 to Bb4
        a4 = 440.0
        bb4 = 440.0 * (2 ** (1/12))
        assert cents_difference(a4, bb4) == pytest.approx(100.0)
        
    def test_just_major_third(self):
        """5/4 ratio is about 386 cents (not 400 like 12-TET)."""
        base = 400.0
        just_third = base * 1.25  # 5/4
        cents = cents_difference(base, just_third)
        assert cents == pytest.approx(386.3, rel=0.01)


class TestPlayableFrequency:
    """Tests for playable_frequency function."""
    
    def test_fundamental_in_target_octave(self):
        """Fundamental (n=1) should be in the target octave."""
        # With f1=54Hz, the fundamental should shift to the target octave
        freq = playable_frequency(54.0, 1, target_octave=4)
        midi = frequency_to_midi_float(freq)
        octave = int(midi // 12) - 1
        assert octave == 4
        
    def test_ratio_preserved(self):
        """The ratio between playable notes should match the reduced harmonic ratios."""
        f1 = 54.0
        target = 4
        
        # Fundamental and perfect fifth (3/2)
        fund_freq = playable_frequency(f1, 1, target)
        fifth_freq = playable_frequency(f1, 3, target)
        
        ratio = fifth_freq / fund_freq
        assert ratio == pytest.approx(1.5)
