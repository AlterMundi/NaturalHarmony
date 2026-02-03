"""Main entry point for The Harmonic Beacon.

Orchestrates MIDI input, harmonic calculation, and OSC output
in a real-time event loop.
"""

import argparse
import math
import signal
import sys
import time
from typing import Optional

from . import config
from .harmonics import (
    beacon_frequency,
    playable_frequency,
    frequency_to_midi_float,
)
from .key_mapper import KeyMapper
from .octave_borrower import OctaveBorrower
from .lfo import HarmonicLFO, VibratoMode
from .midi_handler import MidiHandler
from .osc_sender import OscSender, MockOscSender
from .mpe_sender import MpeSender, MockMpeSender
from .polyphony import VoiceTracker


class F1Modulator:
    """Handles smooth interpolation of the base frequency (f₁).
    
    Prevents digital clicks by interpolating between target values
    rather than jumping instantly.
    """
    
    def __init__(
        self,
        initial: float = config.DEFAULT_F1,
        smoothing_rate: float = config.F1_SMOOTHING_RATE,
        min_freq: float = config.F1_MIN,
        max_freq: float = config.F1_MAX,
    ):
        """Initialize the f₁ modulator.
        
        Args:
            initial: Initial f₁ value in Hz
            smoothing_rate: Interpolation rate (0.0 to 1.0)
            min_freq: Minimum f₁ value in Hz
            max_freq: Maximum f₁ value in Hz
        """
        self.value = initial
        self.target = initial
        self.rate = smoothing_rate
        self.min_freq = min_freq
        self.max_freq = max_freq
        
    def set_target_from_cc(self, cc_value: int) -> None:
        """Set target f₁ from a MIDI CC value (0-127).
        
        Args:
            cc_value: CC value (0-127) to map to frequency range
        """
        # Map CC 0-127 to frequency range
        normalized = cc_value / 127.0
        self.target = self.min_freq + normalized * (self.max_freq - self.min_freq)
        
    def set_target(self, frequency: float) -> None:
        """Set target f₁ directly in Hz.
        
        Args:
            frequency: Target frequency in Hz (clamped to range)
        """
        self.target = max(self.min_freq, min(self.max_freq, frequency))
        
    def update(self) -> bool:
        """Perform one interpolation step.
        
        Returns:
            True if value changed meaningfully (> 0.01 Hz)
        """
        old_value = self.value
        self.value += (self.target - self.value) * self.rate
        return abs(self.value - old_value) > 0.01
    
    @property
    def is_stable(self) -> bool:
        """Whether f₁ has reached its target."""
        return abs(self.value - self.target) < 0.01


class HarmonicBeacon:
    """Main application class for The Harmonic Beacon.
    
    Coordinates MIDI input, harmonic calculation, voice tracking,
    and OSC output in a real-time loop.
    """
    
    def __init__(
        self,
        mock_osc: bool = False,
        broadcast: bool = False,
        enable_mpe: bool = False,
        mock_mpe: bool = False,
        modulation_port_pattern: Optional[str] = config.SECONDARY_MIDI_PORT_PATTERN,
        verbose: bool = True,
    ):
        """Initialize The Harmonic Beacon.
        
        Args:
            mock_osc: If True, use MockOscSender instead of real OSC
            broadcast: If True, broadcast state to visualizer
            enable_mpe: If True, enable MPE output via virtual MIDI port
            mock_mpe: If True, use MockMpeSender for testing
            modulation_port_pattern: Pattern to match secondary MIDI controller name
            verbose: If True, print status messages
        """
        self.verbose = verbose
        self.running = False
        
        # Tolerance and LFO settings
        self.tolerance = config.DEFAULT_TOLERANCE
        self.lfo_rate = config.DEFAULT_LFO_RATE
        self.vibrato_mode = VibratoMode.SMOOTH
        
        # Transpose layer settings (for borrowed keys)
        self.transpose_layer_enabled = True  # Toggled by CC29
        self.transpose_mix = config.DEFAULT_TRANSPOSE_MIX  # 0=beacon, 1=transposed
        
        # Per-note LFOs for harmonic chorus
        self._note_lfos: dict[int, HarmonicLFO] = {}
        self._last_update_time = time.time()
        
        # Initialize components
        self.midi = MidiHandler()
        
        # Secondary MIDI controller for modulation (optional)
        self.modulation_port_pattern = modulation_port_pattern
        self.secondary_midi: Optional[MidiHandler] = None
        if modulation_port_pattern:
            self.secondary_midi = MidiHandler(port_pattern=modulation_port_pattern)
        self.osc: OscSender = MockOscSender(verbose=verbose) if mock_osc else OscSender(broadcast=broadcast)
        self.voices = VoiceTracker()
        self.f1 = F1Modulator()
        
        # MPE output (optional)
        self.mpe_enabled = enable_mpe
        if enable_mpe:
            self.mpe: MpeSender = MockMpeSender(verbose=verbose) if mock_mpe else MpeSender(verbose=verbose)
        else:
            self.mpe = None
        
        # Key mapper for harmonic matching
        self._key_mapper = KeyMapper(
            f1=self.f1.value,
            anchor_midi=config.ANCHOR_MIDI_NOTE,
            tolerance_cents=self.tolerance,
            max_harmonic=config.MAX_HARMONIC,
        )
        
        # Octave borrower for inactive keys
        self._borrower = OctaveBorrower(self._key_mapper)
        
    def start(self) -> None:
        """Start the Harmonic Beacon."""
        # Open primary MIDI port
        port_name = self.midi.open()
        if self.verbose:
            print(f"✓ MIDI: Connected to '{port_name}'")
        
        # Open secondary MIDI port for modulation (non-fatal if unavailable)
        if self.secondary_midi is not None:
            try:
                secondary_port = self.secondary_midi.open()
                if self.verbose:
                    print(f"✓ MIDI (modulation): Connected to '{secondary_port}'")
            except RuntimeError as e:
                if self.verbose:
                    print(f"⚠ MIDI (modulation): No controller found matching '{self.modulation_port_pattern}'")
                self.secondary_midi = None
            
        # Open OSC connection
        self.osc.open()
        if self.verbose:
            print(f"✓ OSC: Targeting {self.osc.host}:{self.osc.port}")
        
        # Open MPE output if enabled
        if self.mpe_enabled and self.mpe is not None:
            mpe_port = self.mpe.open()
            if self.verbose:
                print(f"✓ MPE: Virtual port '{mpe_port}' ready")
        
        if self.verbose:
            print(f"✓ f₁: {self.f1.value:.1f} Hz (range: {self.f1.min_freq}-{self.f1.max_freq} Hz)")
            print("\n🎵 The Harmonic Beacon is active! Press Ctrl+C to stop.\n")
        
        self.running = True
        
    def stop(self) -> None:
        """Stop the Harmonic Beacon and release all resources."""
        self.running = False
        
        # Release all active voices
        self.osc.send_all_notes_off()
        if self.mpe_enabled and self.mpe is not None:
            self.mpe.send_all_notes_off()
        self.voices.clear()
            
        # Close connections
        self.midi.close()
        if self.secondary_midi is not None:
            self.secondary_midi.close()
        self.osc.close()
        if self.mpe_enabled and self.mpe is not None:
            self.mpe.close()
        
        if self.verbose:
            print("\n✓ The Harmonic Beacon has stopped.")
            
    def _handle_note_on(self, note: int, velocity: int) -> None:
        """Handle a Note-On event with tolerance-based harmonic mapping."""
        current_f1 = self.f1.value
        
        # Try direct match first
        match = self._key_mapper.get_match(note)
        borrowed = None
        
        if match is None:
            # No direct match - try octave borrowing
            borrowed = self._borrower.borrow(note)
            if borrowed is None:
                # No match even with borrowing - skip
                if self.verbose:
                    print(f"♪ Note ON: MIDI {note} → (no harmonic match)")
                return
        
        # Get harmonic info from direct match or borrowed
        if match is not None:
            primary_n = match.harmonic_n
            beacon_freq = current_f1 * primary_n
            transposed_freq = None  # No transposition for direct matches
        else:
            primary_n = borrowed.harmonic_n
            beacon_freq = current_f1 * primary_n
            # Calculate octave-transposed frequency (bring down to played octave)
            transposed_freq = beacon_freq / (2 ** borrowed.octaves_borrowed)
        
        playable_freq = playable_frequency(current_f1, primary_n, note)
        
        # Determine if playable voice is needed (different from beacon by more than 1Hz)
        # If they're essentially the same frequency, we only need one voice
        needs_playable_voice = abs(playable_freq - beacon_freq) > 1.0
        
        # Set up LFO (single harmonic, no chorus needed)
        lfo = HarmonicLFO(rate=self.lfo_rate, mode=self.vibrato_mode)
        lfo.set_harmonics([beacon_freq])
        self._note_lfos[note] = lfo
        
        # Calculate velocities based on mix (for borrowed keys with transpose layer)
        if transposed_freq is not None and self.transpose_layer_enabled:
            # Mix: 0.0 = full beacon, 1.0 = full transposed
            beacon_vel = velocity * (1.0 - self.transpose_mix)
            transposed_vel = velocity * self.transpose_mix
        else:
            beacon_vel = velocity
            transposed_vel = 0
        
        # Allocate voices (playable_freq will be same as beacon if not needed separately)
        beacon_id, playable_id = self.voices.note_on(
            note, velocity, 
            beacon_freq=beacon_freq, 
            playable_freq=playable_freq if needs_playable_voice else beacon_freq,
            original_f1=current_f1,
            harmonic_n=primary_n,
        )
        beacon_vel_normalized = beacon_vel / 127.0
        
        # Calculate transposed layer info (for borrowed keys with CC29/CC90)
        transposed_id = -1
        transposed_vel_normalized = 0.0
        if transposed_freq is not None and self.transpose_layer_enabled and transposed_vel > 0:
            transposed_vel_normalized = transposed_vel / 127.0
            # Use playable_id + 1000 as a separate voice ID for transposed layer
            transposed_id = playable_id + 1000
            # Store in voice pair for note_off
            pair = self.voices.get_voice_pair(note)
            if pair is not None:
                pair.transposed_voice_id = transposed_id
                pair.transposed_frequency = transposed_freq
        
        # === Send to OSC ===
        # Always send beacon voice
        self.osc.send_note_on(beacon_id, beacon_freq, beacon_vel_normalized)
        
        # Only send playable voice if it's a different frequency
        if needs_playable_voice:
            self.osc.send_note_on(playable_id, playable_freq, beacon_vel_normalized)
        
        # Send transposed layer if enabled for borrowed keys
        if transposed_id >= 0:
            self.osc.send_note_on(transposed_id, transposed_freq, transposed_vel_normalized)
        
        # Broadcast to visualizer
        self.osc.broadcast_key_on(note, velocity)
        self.osc.broadcast_voice_on(beacon_id, beacon_freq, beacon_vel_normalized, note, primary_n)
        if needs_playable_voice:
            self.osc.broadcast_voice_on(playable_id, playable_freq, beacon_vel_normalized, note, primary_n)
        
        # === Send to MPE (same voices as OSC) ===
        if self.mpe_enabled and self.mpe is not None:
            # Beacon voice
            self.mpe.send_note_on(beacon_id, beacon_freq, beacon_vel_normalized)
            
            # Playable voice (if different)
            if needs_playable_voice:
                self.mpe.send_note_on(playable_id, playable_freq, beacon_vel_normalized)
            
            # Transposed layer
            if transposed_id >= 0:
                self.mpe.send_note_on(transposed_id, transposed_freq, transposed_vel_normalized)
        
        if self.verbose:
            if match is not None:
                sign = '+' if match.deviation_cents >= 0 else ''
                print(f"♪ Note ON: MIDI {note} → n={primary_n} ({sign}{match.deviation_cents:.1f}¢)")
            else:
                print(f"♪ Note ON: MIDI {note} → n={primary_n} [borrowed from MIDI {borrowed.borrowed_midi}]")
                if self.transpose_layer_enabled:
                    print(f"    + Transposed: {transposed_freq:.2f} Hz (mix: {self.transpose_mix:.0%})")
            print(f"    Beacon:   {beacon_freq:.2f} Hz")
            print(f"    Playable: {playable_freq:.2f} Hz")
            
    def _handle_note_off(self, note: int) -> None:
        """Handle a Note-Off event."""
        pair = self.voices.note_off(note)
        if pair is None:
            return
        
        # Clean up LFO for this note
        self._note_lfos.pop(note, None)
        
        # Check if playable voice was different from beacon (same logic as note_on)
        playable_was_active = abs(pair.playable_frequency - pair.beacon_frequency) > 1.0
        
        # Check if transposed layer was active
        transposed_was_active = pair.transposed_voice_id >= 0
        
        # === Send to OSC ===
        # Beacon voice
        self.osc.send_note_off(
            pair.beacon_voice_id, 
            frequency=pair.beacon_frequency
        )
        
        # Playable voice (if it was active)
        if playable_was_active:
            self.osc.send_note_off(
                pair.playable_voice_id,
                frequency=pair.playable_frequency
            )
        
        # Transposed layer (if it was active)
        if transposed_was_active:
            self.osc.send_note_off(
                pair.transposed_voice_id,
                frequency=pair.transposed_frequency
            )
        
        # Broadcast to visualizer
        self.osc.broadcast_key_off(note)
        self.osc.broadcast_voice_off(pair.beacon_voice_id)
        if playable_was_active:
            self.osc.broadcast_voice_off(pair.playable_voice_id)
        
        # === Send to MPE (same voices as OSC) ===
        if self.mpe_enabled and self.mpe is not None:
            # Beacon voice
            self.mpe.send_note_off(pair.beacon_voice_id, frequency=pair.beacon_frequency)
            
            # Playable voice (if it was active)
            if playable_was_active:
                self.mpe.send_note_off(pair.playable_voice_id, frequency=pair.playable_frequency)
            
            # Transposed layer (if it was active)
            if transposed_was_active:
                self.mpe.send_note_off(pair.transposed_voice_id, frequency=pair.transposed_frequency)
        
        if self.verbose:
            print(f"♫ Note OFF: MIDI {note}")
            
    def _handle_f1_change(self, cc_value: int) -> None:
        """Handle f₁ modulation CC."""
        self.f1.set_target_from_cc(cc_value)
        self.osc.broadcast_f1(self.f1.target)
        self.osc.broadcast_cc(config.F1_CC_NUMBER, cc_value)
        if self.verbose:
            print(f"⟳ f₁ target: {self.f1.target:.1f} Hz")
            
    def _update_active_voices(self) -> None:
        """Update all active voices with current f₁ using pitch expressions.
        
        Calculates the semitone offset from each note's original pitch
        and sends Surge XT pitch expressions for real-time sliding.
        """
        current_f1 = self.f1.value
        
        for note, pair in self.voices.get_active_notes().items():
            # Check if playable voice was active (same logic as note_on/off)
            playable_is_active = abs(pair.playable_frequency - pair.beacon_frequency) > 1.0
            
            # Check if transposed layer was active
            transposed_is_active = pair.transposed_voice_id >= 0
            
            # Calculate new frequencies based on current f₁
            new_beacon_freq = beacon_frequency(current_f1, pair.harmonic_n)
            
            # Calculate semitone offset from original beacon frequency
            original_beacon_midi = frequency_to_midi_float(pair.beacon_frequency)
            new_beacon_midi = frequency_to_midi_float(new_beacon_freq)
            beacon_semitone_offset = new_beacon_midi - original_beacon_midi
            
            # === Send to OSC ===
            self.osc.send_pitch_expression(pair.beacon_voice_id, beacon_semitone_offset)
            
            # Playable pitch expression
            playable_semitone_offset = 0.0
            if playable_is_active:
                new_playable_freq = playable_frequency(
                    current_f1, pair.harmonic_n, note
                )
                original_playable_midi = frequency_to_midi_float(pair.playable_frequency)
                new_playable_midi = frequency_to_midi_float(new_playable_freq)
                playable_semitone_offset = new_playable_midi - original_playable_midi
                self.osc.send_pitch_expression(pair.playable_voice_id, playable_semitone_offset)
            
            # Transposed pitch expression (same ratio as beacon)
            if transposed_is_active and pair.transposed_frequency > 0:
                # Transposed frequency scales proportionally with beacon
                new_transposed_freq = pair.transposed_frequency * (new_beacon_freq / pair.beacon_frequency)
                original_transposed_midi = frequency_to_midi_float(pair.transposed_frequency)
                new_transposed_midi = frequency_to_midi_float(new_transposed_freq)
                transposed_semitone_offset = new_transposed_midi - original_transposed_midi
                self.osc.send_pitch_expression(pair.transposed_voice_id, transposed_semitone_offset)
            
            # === Send to MPE (same as OSC) ===
            if self.mpe_enabled and self.mpe is not None:
                self.mpe.send_pitch_expression(pair.beacon_voice_id, beacon_semitone_offset)
                
                if playable_is_active:
                    self.mpe.send_pitch_expression(pair.playable_voice_id, playable_semitone_offset)
                
                if transposed_is_active and pair.transposed_frequency > 0:
                    new_transposed_freq = pair.transposed_frequency * (new_beacon_freq / pair.beacon_frequency)
                    original_transposed_midi = frequency_to_midi_float(pair.transposed_frequency)
                    new_transposed_midi = frequency_to_midi_float(new_transposed_freq)
                    transposed_semitone_offset = new_transposed_midi - original_transposed_midi
                    self.mpe.send_pitch_expression(pair.transposed_voice_id, transposed_semitone_offset)
    
    def _handle_modulation_note(self, note: int) -> None:
        """Handle note from secondary controller - modulate to new root.
        
        When a note is played on the secondary (modulation) controller,
        the keyboard re-orients around that note's pitch class. The new 
        anchor is the same pitch class as the played note, but in the 
        current anchor's octave.
        
        This does NOT produce any sound - it only changes f₁ and anchor.
        
        Args:
            note: MIDI note number from secondary controller
        """
        current_anchor = self._key_mapper.anchor_midi
        
        # Calculate new anchor: same pitch class as played note, 
        # but in the current anchor's octave
        played_pitch_class = note % 12
        anchor_octave = current_anchor // 12
        new_anchor = (anchor_octave * 12) + played_pitch_class
        
        # Calculate semitones from new anchor to played note
        semitones_from_new_anchor = note - new_anchor
        
        # Find the harmonic n at that semitone distance
        target_cents = semitones_from_new_anchor * 100.0
        
        # Find closest harmonic to target_cents
        best_n = 1
        best_diff = float('inf')
        for n in range(1, config.MAX_HARMONIC + 1):
            h_cents = 1200.0 * math.log2(n)
            diff = abs(h_cents - target_cents)
            if diff < best_diff:
                best_diff = diff
                best_n = n
            if h_cents > target_cents + 100:  # Stop if way past
                break
        
        # Calculate new f1 so the played note becomes n=best_n at 12TET frequency
        # For the played MIDI note, calculate its 12TET frequency
        from .harmonics import FREQ_A4, MIDI_A4
        played_freq = FREQ_A4 * (2.0 ** ((note - MIDI_A4) / 12.0))
        
        # new_f1 = played_freq / best_n
        new_f1 = played_freq / best_n
        
        # Transpose to allowed range (preserve pitch class)
        while new_f1 < self.f1.min_freq:
            new_f1 *= 2.0
            new_anchor += 12  # Move anchor up an octave too
        while new_f1 > self.f1.max_freq:
            new_f1 /= 2.0
            new_anchor -= 12  # Move anchor down an octave too
        
        # Set f₁ instantly (no sliding)
        self.f1.value = new_f1
        self.f1.target = new_f1
        
        # Update the key mapper with new anchor and f1
        self._key_mapper.rebuild(f1=new_f1, anchor_midi=new_anchor)
        
        # Update global config anchor for compatibility
        config.ANCHOR_MIDI_NOTE = new_anchor
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        anchor_note = note_names[new_anchor % 12]
        anchor_octave_num = (new_anchor // 12) - 1
        
        if self.verbose:
            print(f"⚓ Modulated: {anchor_note}{anchor_octave_num} is now n=1, f₁ = {new_f1:.1f} Hz")
            print(f"    (from MIDI {note}, n={best_n})")
    
    def _handle_tolerance_change(self, cc_value: int) -> None:
        """Handle tolerance CC (CC67).
        
        Args:
            cc_value: CC value (1-127) maps to TOLERANCE_MIN-TOLERANCE_MAX
        """
        # Map 1-127 to tolerance range (avoid 0 for minimum audible effect)
        normalized = max(1, cc_value) / 127.0
        self.tolerance = (
            config.TOLERANCE_MIN + 
            normalized * (config.TOLERANCE_MAX - config.TOLERANCE_MIN)
        )
        # Rebuild key mapper with new tolerance
        self._key_mapper.rebuild(tolerance_cents=self.tolerance)
        if self.verbose:
            print(f"🎚️ Tolerance: {self.tolerance:.1f}¢")
        self.osc.broadcast_cc(config.TOLERANCE_CC, cc_value)
    
    def _handle_lfo_rate_change(self, cc_value: int) -> None:
        """Handle LFO rate CC (CC68).
        
        Args:
            cc_value: CC value (0-127) maps to LFO_RATE_MIN-LFO_RATE_MAX
        """
        normalized = cc_value / 127.0
        self.lfo_rate = (
            config.LFO_RATE_MIN + 
            normalized * (config.LFO_RATE_MAX - config.LFO_RATE_MIN)
        )
        # Update all active LFOs
        for lfo in self._note_lfos.values():
            lfo.rate = self.lfo_rate
        if self.verbose:
            print(f"🌊 LFO Rate: {self.lfo_rate:.2f} Hz")
        self.osc.broadcast_cc(config.LFO_RATE_CC, cc_value)
    
    def _handle_vibrato_mode_toggle(self, cc_value: int) -> None:
        """Handle vibrato mode toggle (CC23).
        
        Args:
            cc_value: CC value (0=smooth, 127=stepped)
        """
        new_mode = VibratoMode.STEPPED if cc_value >= 64 else VibratoMode.SMOOTH
        
        if new_mode != self.vibrato_mode:
            self.vibrato_mode = new_mode
            # Update all active LFOs
            for lfo in self._note_lfos.values():
                lfo.mode = new_mode
            if self.verbose:
                mode_name = "Stepped ▮▮" if new_mode == VibratoMode.STEPPED else "Smooth 〜"
                print(f"🔄 Vibrato: {mode_name}")
            self.osc.broadcast_cc(config.VIBRATO_MODE_CC, cc_value)
    
    def _handle_transpose_layer_toggle(self, cc_value: int) -> None:
        """Handle transpose layer toggle (CC29).
        
        Args:
            cc_value: CC value (0=disabled, 127=enabled)
        """
        enabled = cc_value >= 64
        if enabled != self.transpose_layer_enabled:
            self.transpose_layer_enabled = enabled
            if self.verbose:
                state = "ON ✓" if enabled else "OFF ✗"
                print(f"🎹 Transpose Layer: {state}")
    
    def _handle_transpose_mix_change(self, cc_value: int) -> None:
        """Handle transpose mix CC (CC90).
        
        Args:
            cc_value: CC value (0=beacon only, 127=transposed only, 64=equal)
        """
        self.transpose_mix = cc_value / 127.0
        if self.verbose:
            beacon_pct = int((1.0 - self.transpose_mix) * 100)
            transposed_pct = int(self.transpose_mix * 100)
            print(f"🎚️ Transpose Mix: {beacon_pct}% beacon / {transposed_pct}% transposed")
    
    def _update_lfo_chorus(self, dt: float) -> None:
        """Update LFO chorus for all active notes.
        
        Args:
            dt: Time delta since last update in seconds
        """
        for note, lfo in self._note_lfos.items():
            if lfo.harmonic_count <= 1:
                continue  # No chorus needed for single harmonic
            
            pair = self.voices.get_active_notes().get(note)
            if pair is None:
                continue
            
            # Get current frequency from LFO
            current_freq = lfo.update(dt)
            
            # Calculate pitch offset from original beacon frequency
            original_midi = frequency_to_midi_float(pair.beacon_frequency)
            current_midi = frequency_to_midi_float(current_freq)
            semitone_offset = current_midi - original_midi
            
            # Send pitch expression
            self.osc.send_pitch_expression(pair.beacon_voice_id, semitone_offset)
            
            # Broadcast frequency update for visualizer
            self.osc.broadcast_voice_freq(pair.beacon_voice_id, current_freq)
            
    def run(self) -> None:
        """Run the main event loop."""
        self.start()
        self._last_update_time = time.time()
        
        try:
            while self.running:
                current_time = time.time()
                dt = current_time - self._last_update_time
                self._last_update_time = current_time
                
                # Update f₁ interpolation
                f1_changed = self.f1.update()
                
                # If f₁ changed, update all active voices
                if f1_changed and self.voices.active_count > 0:
                    self._update_active_voices()
                
                # Update LFO chorus for harmonic sweep
                if self._note_lfos:
                    self._update_lfo_chorus(dt)
                
                # Process MIDI messages
                for msg in self.midi.poll():
                    if self.midi.is_note_on(msg):
                        self._handle_note_on(msg.note, msg.velocity)
                        
                    elif self.midi.is_note_off(msg):
                        self._handle_note_off(msg.note)
                        
                    elif self.midi.is_f1_control(msg):
                        self._handle_f1_change(msg.value)
                    
                    elif self.midi.is_tolerance_control(msg):
                        self._handle_tolerance_change(msg.value)
                    
                    elif self.midi.is_lfo_rate_control(msg):
                        self._handle_lfo_rate_change(msg.value)
                    
                    elif self.midi.is_vibrato_mode_toggle(msg):
                        self._handle_vibrato_mode_toggle(msg.value)
                    
                    elif self.midi.is_transpose_layer_toggle(msg):
                        self._handle_transpose_layer_toggle(msg.value)
                    
                    elif self.midi.is_transpose_mix_control(msg):
                        self._handle_transpose_mix_change(msg.value)
                
                # Poll secondary controller for modulation notes
                if self.secondary_midi is not None:
                    for msg in self.secondary_midi.poll():
                        if self.secondary_midi.is_note_on(msg):
                            # Modulation note - change anchor without producing sound
                            self._handle_modulation_note(msg.note)
                        # Note-off from secondary controller is ignored
                
                # Sleep to avoid busy-waiting
                time.sleep(config.MIDI_POLL_INTERVAL)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main() -> None:
    """Entry point for the Harmonic Beacon CLI."""
    parser = argparse.ArgumentParser(
        description="The Harmonic Beacon - Natural Harmonic Series MIDI Middleware"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock OSC sender (for testing without Surge XT)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List available MIDI input ports and exit",
    )
    parser.add_argument(
        "--f1",
        type=float,
        default=config.DEFAULT_F1,
        help=f"Initial base frequency in Hz (default: {config.DEFAULT_F1})",
    )
    parser.add_argument(
        "--broadcast",
        action="store_true",
        help=f"Broadcast state to visualizer on port {config.BROADCAST_PORT}",
    )
    parser.add_argument(
        "--mpe",
        action="store_true",
        help="Enable MPE output on virtual MIDI port 'Harmonic Beacon MPE'",
    )
    parser.add_argument(
        "--mock-mpe",
        action="store_true",
        help="Use mock MPE sender (for testing without virtual MIDI port)",
    )
    parser.add_argument(
        "--modulation-port",
        type=str,
        default=config.SECONDARY_MIDI_PORT_PATTERN,
        metavar="PATTERN",
        help=f"Pattern to match secondary MIDI controller for modulation (default: '{config.SECONDARY_MIDI_PORT_PATTERN}')",
    )
    parser.add_argument(
        "--no-modulation",
        action="store_true",
        help="Disable secondary MIDI controller for modulation",
    )
    
    args = parser.parse_args()
    
    # List ports mode
    if args.list_ports:
        ports = MidiHandler.list_ports()
        print("Available MIDI input ports:")
        for i, port in enumerate(ports):
            print(f"  [{i}] {port}")
        if not ports:
            print("  (none)")
        return
    
    # Determine modulation port
    modulation_port = None if args.no_modulation else args.modulation_port
    
    # Create and run the beacon
    beacon = HarmonicBeacon(
        mock_osc=args.mock,
        broadcast=args.broadcast,
        enable_mpe=args.mpe or args.mock_mpe,
        mock_mpe=args.mock_mpe,
        modulation_port_pattern=modulation_port,
        verbose=not args.quiet,
    )
    beacon.f1.value = args.f1
    beacon.f1.target = args.f1
    
    # Handle signals gracefully
    def signal_handler(sig, frame):
        beacon.running = False
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    beacon.run()


if __name__ == "__main__":
    main()
