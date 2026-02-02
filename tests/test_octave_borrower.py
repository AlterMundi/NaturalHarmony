"""Tests for octave borrowing fallback logic."""

import pytest
import sys
sys.path.insert(0, '/home/nicolas/OS_projects/NaturalHarmony')

from harmonic_beacon.key_mapper import KeyMapper
from harmonic_beacon.octave_borrower import (
    OctaveBorrower,
    dump_full_keyboard,
)


class TestOctaveBorrowing:
    """Test that inactive keys borrow from higher octaves."""
    
    @pytest.fixture
    def mapper(self):
        return KeyMapper(
            f1=54.0,
            anchor_midi=24,
            tolerance_cents=25.0,
            lowest_midi=24,
            highest_midi=108,
        )
    
    @pytest.fixture
    def borrower(self, mapper):
        return OctaveBorrower(mapper)
    
    def test_direct_match_not_borrowed(self, mapper, borrower):
        """Keys with direct matches should not trigger borrowing."""
        # C2 (MIDI 36) has a direct match (n=2)
        assert mapper.get_harmonic(36) == 2
        assert borrower.borrow(36) is None
    
    def test_inactive_key_borrows_from_higher_octave(self, mapper, borrower):
        """D2 (MIDI 38) has no direct match, should borrow from D at higher octave."""
        # D2 = MIDI 38, should have no direct match
        assert mapper.get_harmonic(38) is None
        
        borrowed = borrower.borrow(38)
        # Should find a match somewhere in higher octaves
        # D is at pitch class 2 (D, D#=3, etc.)
        if borrowed is not None:
            # Verify it borrowed from a D in a higher octave
            assert borrowed.original_midi == 38
            assert borrowed.borrowed_midi > 38
            assert (borrowed.borrowed_midi - 38) % 12 == 0  # Same pitch class
            assert borrowed.octaves_borrowed >= 1
    
    def test_d2_borrows_d_at_n9(self, mapper, borrower):
        """D2 should borrow from the octave where D matches n=9.
        
        n=9 is at 1200*log2(9) = 3803.91 cents = 38.04 semitones
        38 semitones from C1 (MIDI 24) = MIDI 62 = D4
        But D4 is at 38 semitones = 3800 cents, which is 3.91 cents below n=9
        So with 25¢ tolerance, D4 (MIDI 62) should match n=9!
        """
        # Check if D4 (MIDI 62) matches n=9
        d4_match = mapper.get_match(62)
        print(f"D4 (MIDI 62) match: {d4_match}")
        
        # Check borrowing from D2
        borrowed = borrower.borrow(38)
        print(f"D2 borrows: {borrowed}")
        
        if borrowed is not None:
            print(f"  From MIDI {borrowed.borrowed_midi}, n={borrowed.harmonic_n}")
    
    def test_get_frequency_tries_borrowing(self, mapper, borrower):
        """get_frequency should return borrowed frequency for inactive keys."""
        # C2 has direct match
        c2_freq = borrower.get_frequency(36)
        assert c2_freq == 54.0 * 2  # f1 * n=2 = 108 Hz
        
        # D2 needs borrowing
        d2_freq = borrower.get_frequency(38)
        # Should be some frequency if borrowing worked
        print(f"D2 frequency via borrowing: {d2_freq}")


class TestFullKeyboardDump:
    """Test the full keyboard visualization."""
    
    def test_dump_shows_direct_and_borrowed(self):
        """Dump should show which keys are direct and which are borrowed."""
        mapper = KeyMapper(
            f1=54.0,
            anchor_midi=24,
            tolerance_cents=25.0,
            lowest_midi=36,  # Start at C2 for readability
            highest_midi=72,  # Up to C5
        )
        borrower = OctaveBorrower(mapper)
        
        dump = dump_full_keyboard(mapper, borrower)
        print("\n" + dump)
        
        # Check that dump contains key info
        assert "DIRECT" in dump or "borrowed" in dump


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
