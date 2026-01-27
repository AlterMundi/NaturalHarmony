"""LFO for harmonic chorus sweep effect.

Sweeps (smooth or stepped) through a list of harmonic frequencies,
creating vibrato/chorus based on the available harmonics.
"""

import math
from enum import Enum


class VibratoMode(Enum):
    """Vibrato interpolation mode."""
    SMOOTH = 0   # Continuous interpolation between harmonics
    STEPPED = 1  # Discrete jumps between harmonics


class HarmonicLFO:
    """LFO that sweeps through a list of harmonic frequencies.
    
    When multiple harmonics match a key's position, this LFO cycles
    through them to create a chorus/vibrato effect.
    """
    
    def __init__(
        self,
        rate: float = 1.0,
        mode: VibratoMode = VibratoMode.SMOOTH,
    ):
        """Initialize the harmonic LFO.
        
        Args:
            rate: LFO frequency in Hz
            mode: Smooth or stepped interpolation
        """
        self.rate = rate
        self.mode = mode
        self.phase = 0.0  # 0.0 to 1.0
        self._frequencies: list[float] = []
        self._base_frequency: float = 440.0
        
    def set_harmonics(self, frequencies: list[float]) -> None:
        """Set the list of frequencies to sweep through.
        
        Args:
            frequencies: List of harmonic frequencies in Hz
        """
        self._frequencies = frequencies if frequencies else [440.0]
        if len(self._frequencies) == 1:
            self._base_frequency = self._frequencies[0]
        else:
            # Use geometric mean as base for reference
            product = 1.0
            for f in self._frequencies:
                product *= f
            self._base_frequency = product ** (1.0 / len(self._frequencies))
    
    def update(self, dt: float) -> float:
        """Advance the LFO and return current frequency.
        
        Args:
            dt: Time delta in seconds
            
        Returns:
            Current frequency in Hz
        """
        if len(self._frequencies) <= 1:
            return self._frequencies[0] if self._frequencies else 440.0
        
        # Advance phase
        self.phase += self.rate * dt
        self.phase = self.phase % 1.0  # Wrap to [0, 1)
        
        # Triangle wave: 0→1→0 over one cycle
        triangle = 1.0 - abs(2.0 * self.phase - 1.0)
        
        if self.mode == VibratoMode.STEPPED:
            # Stepped: quantize to discrete harmonic indices
            n = len(self._frequencies)
            index = int(triangle * n)
            index = min(index, n - 1)  # Clamp
            return self._frequencies[index]
        else:
            # Smooth: interpolate between frequencies
            n = len(self._frequencies)
            position = triangle * (n - 1)
            lower_idx = int(position)
            upper_idx = min(lower_idx + 1, n - 1)
            frac = position - lower_idx
            
            # Linear interpolation in log space (sounds more natural)
            log_lower = math.log2(self._frequencies[lower_idx])
            log_upper = math.log2(self._frequencies[upper_idx])
            log_result = log_lower + frac * (log_upper - log_lower)
            return 2.0 ** log_result
    
    def get_pitch_offset_semitones(self, dt: float) -> float:
        """Get the current pitch offset from base frequency in semitones.
        
        Args:
            dt: Time delta in seconds (0 to just read current value)
            
        Returns:
            Pitch offset in semitones
        """
        if dt > 0:
            current_freq = self.update(dt)
        else:
            current_freq = self.current_frequency
        
        if current_freq <= 0 or self._base_frequency <= 0:
            return 0.0
        return 12.0 * math.log2(current_freq / self._base_frequency)
    
    @property
    def current_frequency(self) -> float:
        """Get current frequency without advancing phase."""
        if len(self._frequencies) <= 1:
            return self._frequencies[0] if self._frequencies else 440.0
        
        triangle = 1.0 - abs(2.0 * self.phase - 1.0)
        n = len(self._frequencies)
        
        if self.mode == VibratoMode.STEPPED:
            index = min(int(triangle * n), n - 1)
            return self._frequencies[index]
        else:
            position = triangle * (n - 1)
            lower_idx = int(position)
            upper_idx = min(lower_idx + 1, n - 1)
            frac = position - lower_idx
            
            log_lower = math.log2(self._frequencies[lower_idx])
            log_upper = math.log2(self._frequencies[upper_idx])
            return 2.0 ** (log_lower + frac * (log_upper - log_lower))
    
    @property
    def base_frequency(self) -> float:
        """The reference frequency (geometric mean of harmonics)."""
        return self._base_frequency
    
    @property
    def harmonic_count(self) -> int:
        """Number of harmonics in the sweep."""
        return len(self._frequencies)
