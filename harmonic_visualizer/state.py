"""State manager for visualizer.

Tracks all state received from Harmonic Beacon broadcasts.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VoiceState:
    """State of a single voice."""
    voice_id: int
    frequency: float
    gain: float
    source_note: int = 60  # MIDI note that triggered this voice
    active: bool = True
    glow: float = 1.0  # Fade-out animation (1.0 = full, 0.0 = gone)


@dataclass
class VisualizerState:
    """Complete visualizer state.
    
    All state is passively updated from OSC broadcasts.
    The visualizer never calculates frequencies - only displays what it receives.
    """
    
    # Base frequency
    f1: float = 32.7  # C1
    anchor_note: int = 60  # C4
    
    # Active voices (voice_id -> VoiceState)
    voices: dict[int, VoiceState] = field(default_factory=dict)
    
    # Pressed keys (note -> velocity)
    pressed_keys: dict[int, int] = field(default_factory=dict)
    
    # CC values (cc_num -> value)
    cc_values: dict[int, int] = field(default_factory=dict)
    
    # Recently released voices for fade-out animation
    fading_voices: dict[int, VoiceState] = field(default_factory=dict)
    
    def voice_on(self, voice_id: int, freq: float, gain: float, source_note: int) -> None:
        """Register a voice activation."""
        self.voices[voice_id] = VoiceState(
            voice_id=voice_id,
            frequency=freq,
            gain=gain,
            source_note=source_note,
        )
        # Remove from fading if re-triggered
        self.fading_voices.pop(voice_id, None)
    
    def voice_off(self, voice_id: int) -> None:
        """Register a voice release (starts fade-out)."""
        if voice_id in self.voices:
            voice = self.voices.pop(voice_id)
            voice.active = False
            self.fading_voices[voice_id] = voice
    
    def voice_freq(self, voice_id: int, freq: float) -> None:
        """Update voice frequency (LFO sweep)."""
        if voice_id in self.voices:
            self.voices[voice_id].frequency = freq
    
    def key_on(self, note: int, velocity: int) -> None:
        """Register a key press."""
        self.pressed_keys[note] = velocity
    
    def key_off(self, note: int) -> None:
        """Register a key release."""
        self.pressed_keys.pop(note, None)
    
    def update_cc(self, cc_num: int, value: int) -> None:
        """Update CC value."""
        self.cc_values[cc_num] = value
    
    def update_fading(self, dt: float, fade_speed: float) -> None:
        """Update fading voices, remove fully faded ones."""
        to_remove = []
        for voice_id, voice in self.fading_voices.items():
            voice.glow -= fade_speed * dt
            if voice.glow <= 0:
                to_remove.append(voice_id)
        for voice_id in to_remove:
            del self.fading_voices[voice_id]
    
    def get_active_frequencies(self) -> list[float]:
        """Get all currently sounding frequencies."""
        return [v.frequency for v in self.voices.values()]
    
    def get_all_visible_voices(self) -> list[VoiceState]:
        """Get all voices (active + fading) for rendering."""
        return list(self.voices.values()) + list(self.fading_voices.values())
