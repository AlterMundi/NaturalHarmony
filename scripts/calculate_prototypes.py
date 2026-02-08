import math

def harmonic_to_cents(n):
    return 1200.0 * math.log2(n)

def calculate_prototypes():
    print("Calculating optimal harmonic prototypes for 1 chromatic octave...")
    
    # 12 chromatic intervals (0=Root, 1=Min2, ... 11=Maj7)
    # We want to find the lowest n that maps to this interval class with minimal error.
    # Error metrics: deviation from 12TET target.
    # We prefer lower n if deviations are comparable.

    matches = {}
    
    for interval in range(12):
        best_n = 1
        best_diff = float('inf')
        best_octave_offset = 0
        
        # Search up to n=64 (sufficient for basic scale construction)
        # We can go higher if needed, e.g. 128
        for n in range(1, 128):
            cents = harmonic_to_cents(n)
            
            # Find which octave of the interval this harmonic lands in
            # n_cents = (octave * 1200) + (interval * 100) + error
            
            # Reduce harmonic cents to one octave range (0-1200) relative to its own octave
            eff_cents = cents % 1200.0
            
            # Target cents for this interval
            target_cents = interval * 100.0
            
            # Compare efficiently
            # We face cyclic distance: 1100 vs 0 is 100 diff, but we are looking for alignment
            # Actually, we want n to be recognized AS this interval.
            # So its Reduced Cents should be closest to Target Cents.
            
            diff = abs(eff_cents - target_cents)
            if diff > 600: # Wrap around (e.g. 1190 vs 0)
                diff = 1200 - diff
                
            if diff < best_diff:
                best_diff = diff
                best_n = n
                best_octave_offset = int(cents // 1200)
            
            # Tie breaking: if diff is very close (within 1 cent), prefer lower n is implicit by loop order
            
        print(f"Interval {interval:2d}: n={best_n:3d} (Dev: {best_diff:5.2f}c) -> Reduced Cents: {harmonic_to_cents(best_n)%1200:6.2f}")
        matches[interval] = best_n

    return matches

if __name__ == "__main__":
    calculate_prototypes()
