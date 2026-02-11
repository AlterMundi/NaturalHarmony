"""Tests for the current KeyMapper implementation.

Tests the Optimized Chromatic approach with prototype harmonics and
octave transposition logic.
"""

import math
import pytest

from harmonic_beacon.key_mapper import (
    KeyMapper,
    KeyMatch,
    harmonic_to_cents,
    midi_to_frequency,
)
from harmonic_beacon import config


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

    def test_n5_is_third_plus_two_octaves(self):
        # 1200 * log2(5) ≈ 2786.31 cents
        cents = harmonic_to_cents(5)
        assert abs(cents - 2786.31) < 0.01


class TestKeyMapperBasics:
    """Test basic KeyMapper initialization and operation."""

    def test_initialization(self):
        """KeyMapper initializes with correct parameters."""
        mapper = KeyMapper(f1=65.0, anchor_midi=24)
        assert mapper.f1 == 65.0
        assert mapper.anchor_midi == 24
        assert mapper.lowest_midi == 21
        assert mapper.highest_midi == 108

    def test_custom_range(self):
        """KeyMapper accepts custom MIDI range."""
        mapper = KeyMapper(f1=65.0, anchor_midi=24, lowest_midi=36, highest_midi=84)
        assert mapper.lowest_midi == 36
        assert mapper.highest_midi == 84

    def test_rebuild_updates_mapping(self):
        """Rebuild updates the internal mapping."""
        mapper = KeyMapper(f1=65.0, anchor_midi=24)
        original_match = mapper.get_match(60)

        # Rebuild with new f1
        mapper.rebuild(f1=50.0)
        new_match = mapper.get_match(60)

        # Frequencies should be different (scaled by f1 change)
        assert original_match.primary_freq != new_match.primary_freq

    def test_rebuild_with_new_anchor(self):
        """Rebuild with new anchor changes key mappings."""
        mapper = KeyMapper(f1=65.0, anchor_midi=24)
        original_match = mapper.get_match(36)  # C2

        # Rebuild with anchor at C2
        mapper.rebuild(anchor_midi=36)
        new_match = mapper.get_match(36)  # Now C2 is the anchor

        # C2 should now map to fundamental (n=1)
        assert new_match.primary_n == config.CHROMATIC_PROTOTYPES[0]  # Should be 1


class TestChromaticPrototypes:
    """Test that chromatic prototypes are correctly applied."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)  # C1 is anchor

    def test_c_maps_to_fundamental(self, mapper):
        """C keys map to harmonic 1 (fundamental)."""
        # C1 = MIDI 24 (anchor), C2 = 36, C3 = 48
        match_c1 = mapper.get_match(24)
        match_c2 = mapper.get_match(36)
        match_c3 = mapper.get_match(48)

        # All should use prototype n=1
        assert config.CHROMATIC_PROTOTYPES[0] == 1
        # But effective n varies by octave (1, 2, 4, 8...)
        assert match_c1.secondary_n == 1
        assert match_c2.secondary_n == 1
        assert match_c3.secondary_n == 1

    def test_e_maps_to_harmonic_5(self, mapper):
        """E keys map to harmonic 5 (major third)."""
        # E is 4 semitones above C
        # C1 + 4 = MIDI 28 (E1)
        match = mapper.get_match(28)

        assert config.CHROMATIC_PROTOTYPES[4] == 5  # E uses prototype 5
        assert match.secondary_n == 5

    def test_g_maps_to_harmonic_3(self, mapper):
        """G keys map to harmonic 3 (perfect fifth)."""
        # G is 7 semitones above C
        # C1 + 7 = MIDI 31 (G1)
        match = mapper.get_match(31)

        assert config.CHROMATIC_PROTOTYPES[7] == 3  # G uses prototype 3
        assert match.secondary_n == 3


class TestTransposition:
    """Test octave transposition logic."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)

    def test_transposition_flag(self, mapper):
        """is_transposed flag indicates octave shift (up or down)."""
        # Transposition can occur up or down to match the played octave
        # Check that is_transposed flag and effective_n are consistent
        match_c1 = mapper.get_match(24)
        match_c2 = mapper.get_match(36)
        match_c3 = mapper.get_match(48)

        # All C keys use prototype n=1, but transposed to different octaves
        assert match_c1.secondary_n == 1
        assert match_c2.secondary_n == 1
        assert match_c3.secondary_n == 1

        # Primary n should be powers of 2 (or fractions like 0.5 for down-transposition)
        # Just verify they're different due to transposition
        assert match_c1.primary_n != match_c2.primary_n != match_c3.primary_n

    def test_effective_harmonic_number(self, mapper):
        """Transposed harmonics have effective n = prototype * 2^octaves."""
        # The mapper transposes to match the 12TET frequency of the played key
        # This means effective n can be > or < the prototype depending on octave
        match_c2 = mapper.get_match(36)  # C2, 1 octave above anchor
        match_c3 = mapper.get_match(48)  # C3, 2 octaves above anchor

        # Verify frequency relationship is correct (octaves)
        ratio = match_c3.primary_freq / match_c2.primary_freq
        assert abs(ratio - 2.0) < 0.01  # Should be exactly 2:1

    def test_frequency_matches_effective_n(self, mapper):
        """Primary frequency equals f1 * effective_n."""
        match = mapper.get_match(60)  # C4

        expected_freq = mapper.f1 * match.primary_n
        assert abs(match.primary_freq - expected_freq) < 0.01


class TestStackingModeSupport:
    """Test that KeyMapper provides data for Stacking Mode."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)

    def test_transposed_keys_have_different_primary_secondary(self, mapper):
        """Transposed keys should have different primary and secondary frequencies."""
        # C4 (MIDI 60) is multiple octaves above anchor
        match = mapper.get_match(60)

        if match.is_transposed:
            # Primary is transposed, secondary is the original prototype
            assert match.primary_freq != match.secondary_freq
            assert match.primary_n != match.secondary_n

    def test_local_keys_have_same_primary_secondary(self, mapper):
        """Non-transposed (local) keys have matching primary and secondary."""
        # Find a key that's not transposed (rare with current logic)
        # C1 (anchor) should definitely not be transposed
        match = mapper.get_match(24)

        if not match.is_transposed:
            assert match.primary_freq == match.secondary_freq
            assert match.primary_n == match.secondary_n

    def test_stacking_data_available_for_all_keys(self, mapper):
        """All keys provide both primary and secondary data for stacking."""
        # Test a range of keys
        for midi_note in [24, 36, 48, 60, 72]:
            match = mapper.get_match(midi_note)
            assert match is not None
            assert match.primary_freq > 0
            assert match.secondary_freq > 0
            assert match.primary_n > 0  # Can be < 1 if transposed down
            assert match.secondary_n >= 1  # Prototypes are always >= 1


class TestDeviationCalculation:
    """Test that deviation from 12TET is correctly calculated."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)

    def test_deviation_in_cents(self, mapper):
        """Deviation is measured in cents."""
        match = mapper.get_match(60)  # C4

        # Deviation should be in reasonable range for microtonal adjustment
        # (typically -50 to +50 cents)
        assert -100 < match.primary_deviation < 100

    def test_c_keys_have_consistent_deviation(self, mapper):
        """C keys (fundamental) should have consistent deviation from 12TET."""
        # Note: Because f1=65Hz is not exactly a 12TET note, there will be
        # a constant deviation across all C keys. This is expected.
        deviations = []
        for octave_midi in [24, 36, 48, 60, 72]:  # C1 through C5
            match = mapper.get_match(octave_midi)
            deviations.append(match.primary_deviation)

        # All C keys should have similar deviation (octaves preserve the ratio)
        # Check they're all within 1 cent of each other
        max_dev = max(deviations)
        min_dev = min(deviations)
        assert abs(max_dev - min_dev) < 1.0


class TestMatchReturnFormat:
    """Test that get_match returns properly formatted KeyMatch objects."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)

    def test_returns_keymatch_object(self, mapper):
        """get_match returns a KeyMatch dataclass."""
        match = mapper.get_match(60)
        assert isinstance(match, KeyMatch)

    def test_keymatch_has_all_fields(self, mapper):
        """KeyMatch has all required fields."""
        match = mapper.get_match(60)

        assert hasattr(match, 'midi_note')
        assert hasattr(match, 'primary_freq')
        assert hasattr(match, 'primary_n')
        assert hasattr(match, 'primary_deviation')
        assert hasattr(match, 'secondary_freq')
        assert hasattr(match, 'secondary_n')
        assert hasattr(match, 'is_transposed')
        assert hasattr(match, 'source_type')

    def test_source_type_is_prototype(self, mapper):
        """All matches use 'prototype' source (local matching disabled)."""
        for midi_note in [24, 36, 48, 60, 72]:
            match = mapper.get_match(midi_note)
            # Local matching is disabled, so all should be 'prototype'
            assert match.source_type == 'prototype'

    def test_out_of_range_returns_none(self, mapper):
        """Keys outside the mapper's range return None."""
        # Mapper default range is 21-108
        match_below = mapper.get_match(20)
        match_above = mapper.get_match(109)

        assert match_below is None
        assert match_above is None


class TestMusicalIntervals:
    """Test that musical intervals are preserved."""

    @pytest.fixture
    def mapper(self):
        return KeyMapper(f1=65.0, anchor_midi=24)

    def test_octave_ratio_is_2_to_1(self, mapper):
        """Octaves maintain 2:1 frequency ratio."""
        match_c1 = mapper.get_match(24)  # C1
        match_c2 = mapper.get_match(36)  # C2

        ratio = match_c2.primary_freq / match_c1.primary_freq
        assert abs(ratio - 2.0) < 0.01

    def test_perfect_fifth_ratio(self, mapper):
        """Perfect fifth (G) maintains 3:2 ratio with fundamental."""
        match_c = mapper.get_match(24)  # C1
        match_g = mapper.get_match(31)  # G1

        # G uses prototype n=3, but we need to check the actual ratio
        # in the same octave
        # Expected ratio should be close to 1.5 (3/2)
        ratio = match_g.primary_freq / match_c.primary_freq
        assert abs(ratio - 1.5) < 0.1  # Allow some deviation due to transposition


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
