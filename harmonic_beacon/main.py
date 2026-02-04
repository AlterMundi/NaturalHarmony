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

import mido # MIDI support

from . import config
from .harmonics import (
    beacon_frequency,
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
        midi_debug: bool = False,
    ):
        """Initialize The Harmonic Beacon.
        
        Args:
            mock_osc: If True, use MockOscSender instead of real OSC
            broadcast: If True, broadcast state to visualizer
            enable_mpe: If True, enable MPE output via virtual MIDI port
            mock_mpe: If True, use MockMpeSender for testing
            modulation_port_pattern: Pattern to match secondary MIDI controller name
            verbose: If True, print status messages
            midi_debug: If True, print all incoming MIDI messages
        """
        self.verbose = verbose
        self.running = False
        
        # Tolerance and LFO settings
        self.tolerance = config.DEFAULT_TOLERANCE
        self.lfo_rate = config.DEFAULT_LFO_RATE
        self.vibrato_mode = VibratoMode.SMOOTH
        
        # Multi-harmonic mode settings (CC29 toggle, CC90 count)
        self.multi_harmonic_enabled = False  # Toggled by CC29
        self.max_harmonics = config.DEFAULT_MAX_HARMONICS  # How many octave harmonics to play
        
        # Harmonic mix settings (CC28 lock, CC89 mix)
        self.primary_lock = True  # If True, primary voice is always loud
        self.harmonic_mix = 0.5   # 0=Secondary Only, 1=Primary Only (if lock OFF)
        
        # Natural Harmonics settings (CC30 toggle, CC92 level)
        self.natural_harmonics_enabled = False # Toggled by CC30
        # Natural Harmonics settings (CC30 toggle, CC92 level)
        self.natural_harmonics_enabled = False # Toggled by CC30
        self.natural_harmonics_level = config.DEFAULT_NATURAL_LEVEL
        
        # Pad Mode (Akai Force)
        self.pad_mode_enabled = config.PAD_MODE_ENABLED_BY_DEFAULT
        self.split_mode_enabled = config.SPLIT_MODE_ENABLED_BY_DEFAULT
        self.toggled_harmonics: set[int] = set() # For Split Mode latching


        
        # Per-note LFOs for harmonic chorus
        self._note_lfos: dict[int, HarmonicLFO] = {}
        self._last_update_time = time.time()
        
        # Initialize components
        self.midi = MidiHandler(debug=midi_debug)
        
        # Secondary MIDI controller for modulation (optional)
        self.modulation_port_pattern = modulation_port_pattern
        self.secondary_midi: Optional[MidiHandler] = None
        if modulation_port_pattern:
            self.secondary_midi = MidiHandler(port_pattern=modulation_port_pattern, debug=midi_debug)
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

    def _play_harmonic(self, midi_note: int, harmonic_n: int, velocity: int, channel: int = 0) -> None:
        """Helper to play a single harmonic (used by Pad Mode)."""
        current_f1 = self.f1.value
        frequency = current_f1 * harmonic_n
        
        voice_ids = self.voices.note_on(
            midi_note, velocity,
            frequencies=[frequency],
            harmonic_ns=[harmonic_n],
            original_f1=current_f1
        )
        
        if voice_ids:
            vid = voice_ids[0]
            vel_norm = velocity / 127.0
            self.osc.send_note_on(vid, frequency, vel_norm)
            self.osc.broadcast_voice_on(vid, frequency, vel_norm, midi_note, harmonic_n)
        
        if self.mpe_enabled and self.mpe is not None and voice_ids:
            self.mpe.send_note_on(voice_ids[0], frequency, vel_norm)

    def panic(self) -> None:
        """Kill all active notes and reset state (Panic)."""
        if self.verbose:
            print("\n🚨 PANIC! Stopping all notes. 🚨\n")
            
        # 1. Stop all tracked voices
        active_notes = list(self.voices.get_active_notes().keys())
        for note in active_notes:
            self._handle_note_off(note)
            
        # 2. Force clear everything just in case
        self.voices.clear()
        self.osc.send_all_notes_off()
        if self.mpe_enabled and self.mpe is not None:
             self.mpe.send_all_notes_off()
             
        # 3. Clear Split Mode Toggles
        self.toggled_harmonics.clear()
        
        # 4. Turn off all lights (Launchpad Reset)
        if self.pad_mode_enabled:
            for n in range(128):
                self.midi.send_message(mido.Message('note_off', note=n, velocity=0, channel=0))
        self.voices.clear()
        self._note_lfos.clear()
        self.osc.send_all_notes_off()
        if self.mpe_enabled and self.mpe is not None:
            self.mpe.send_all_notes_off()

    def _handle_split_mode_toggle(self, value: int) -> None:
        """Handle Split Mode Toggle (CC 104)."""
        if value > 0:
            self.split_mode_enabled = not self.split_mode_enabled
            if self.verbose:
                state = "ON" if self.split_mode_enabled else "OFF"
                print(f"🎛️ Split Mode: {state}")
            
            # Reset state when determining mode
            self.toggled_harmonics.clear()
            self.voices.clear()
            self.osc.send_all_notes_off()
            if self.mpe:
                self.mpe.send_all_notes_off()

    def _handle_note_on(self, note: int, velocity: int, channel: int = 0) -> None:
        """Handle a Note-On event with tolerance-based harmonic mapping.
        
        Supports two modes:
        1. Pad Mode: Direct mapping of 64 pads to harmonics 1-64.
        2. Keyboard Mode: Standard tolerance-based mapping with Atmosphere/Natural layers.
        """
        current_f1 = self.f1.value
        
        # --- Check for Panic ---
        if note == config.PANIC_NOTE:
            self.panic()
            return
        
        # --- Check for Mode Toggle ---
        if note == config.PAD_MODE_TOGGLE_NOTE:
            self.pad_mode_enabled = not self.pad_mode_enabled
            if self.verbose:
                state = "PAD MODE" if self.pad_mode_enabled else "KEYBOARD MODE"
                print(f"\n🎛️ Switched to: {state}\n")
            
            # Broadcast state to visualizer
            self.osc.broadcast_pad_mode(self.pad_mode_enabled)
            
            # Don't play sound for the toggle button
            return

        # =========================================================================
        # MODE 1: PAD MODE (Direct Harmonic Mapping)
        # =========================================================================
        if self.pad_mode_enabled:
            # Determine Mapping
            layout = getattr(config, 'PAD_MAP_TYPE', 'LINEAR')
            n = 0
            is_toggle_action = False
            feedback_color = config.PAD_FEEDBACK_COLOR_ON
            
            if layout == 'LAUNCHPAD':
                # Launchpad XY Layout (Stride 16)
                rel = note - config.PAD_ANCHOR_NOTE
                if rel >= 0:
                    x = rel % 16
                    y = rel // 16
                    if x < 8 and y < 8:
                        # Invert Y so harmonic 1 is at Bottom-Left (Row 0)
                        row_from_bottom = 7 - y
                        
                        if self.split_mode_enabled:
                             if row_from_bottom < 4:
                                 # Lower Half (Rows 0-3): Momentary 1-32
                                 n = 1 + x + (row_from_bottom * 8)
                             else:
                                 # Upper Half (Rows 4-7): Toggle 1-32
                                 n = 1 + x + ((row_from_bottom - 4) * 8)
                                 is_toggle_action = True
                                 feedback_color = getattr(config, 'PAD_FEEDBACK_COLOR_TOGGLE_ON', 21)
                        else:
                             # Full Mode: 1-64
                             n = 1 + x + (row_from_bottom * 8)
            else:
                # Linear Mapping (Force/Generic)
                n = 1 + (note - config.PAD_ANCHOR_NOTE)
            
            # Validity check
            if 1 <= n <= 64:
                # --- Toggle Logic ---
                if is_toggle_action:
                    if n in self.toggled_harmonics:
                        # Turn OFF Logic
                        self.toggled_harmonics.discard(n)
                        if self.verbose:
                            print(f"🎛️ Pad {note}: Toggle OFF (n={n})")
                        
                        # Kill triggers
                        pair = self.voices.note_off(note)
                        if pair:
                            self._note_lfos.pop(note, None)
                            for i, voice_id in enumerate(pair.voice_ids):
                                freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
                                self.osc.send_note_off(voice_id, frequency=freq)
                                self.osc.broadcast_voice_off(voice_id)
                            self.osc.broadcast_key_off(note)
                            if self.mpe_enabled and self.mpe:
                                for i, voice_id in enumerate(pair.voice_ids):
                                    freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
                                    self.mpe.send_note_off(voice_id, frequency=freq)
                                    
                        # Turn off light
                        self.midi.send_message(mido.Message('note_off', note=note, velocity=0, channel=channel))
                        return
                    else:
                        # Turn ON Logic
                        self.toggled_harmonics.add(n)
                        if self.verbose:
                             print(f"🎛️ Pad {note}: Toggle ON (n={n})")
                        # Fall through to Play Logic
                
                # --- Play Logic ---
                # Direct harmonic mapping
                self._play_harmonic(note, n, velocity, channel)
                if self.verbose and not is_toggle_action:
                    print(f"🎛️ Pad {note}: Harmonic {n} ({n*current_f1:.1f} Hz)")
                
                # Feedback: Light up the pad
                self.midi.send_message(mido.Message(
                    'note_on', 
                    note=note, 
                    velocity=feedback_color,
                    channel=channel
                ))
            else:
                if self.verbose:
                    print(f"🎛️ Pad {note}: Ignored (n={n})")
            return
        
        # =========================================================================
        # MODE 2: KEYBOARD MODE (Standard)
        # =========================================================================
        
        # --- 1. Determine Primary Match ---
        match = self._key_mapper.get_match(note)
        borrowed = None
        
        if match is None:
            borrowed = self._borrower.borrow(note)
            if borrowed is None:
                if self.verbose:
                    print(f"♪ Note ON: MIDI {note} → (no harmonic match)")
                return
        
        # Lists to populate
        frequencies: list[float] = []
        harmonic_ns: list[int] = []
        target_gains: list[float] = []
        
        # --- 2. Add Primary Voice ---
        if match is not None:
            # Direct match
            primary_n = match.harmonic_n
            primary_freq = current_f1 * primary_n
            
            frequencies.append(primary_freq)
            harmonic_ns.append(primary_n)
            
            # Start checks from next octave
            check_note_atmosphere = note + 12
            check_note_natural = note + 12
        else:
            # Borrowed
            primary_n = borrowed.harmonic_n
            beacon_freq = current_f1 * primary_n
            transposed_freq = beacon_freq / (2 ** borrowed.octaves_borrowed)
            
            frequencies.append(transposed_freq)
            harmonic_ns.append(primary_n)
            
            # Start checks from source octave
            source_note = note + (12 * borrowed.octaves_borrowed)
            check_note_atmosphere = source_note  # For folding, we scan from source
            check_note_natural = source_note     # For natural, we scan from source
            # Actually for Natural, if we are playing C3 (borrowed from C4), 
            # we want natural harmonics of C3? Or C4?
            # If we play C3, we want to hear the timbre of C3.
            # But C3 is "fake" (borrowed).
            # The "Natural" logic scans for matches in *played* key context usually.
            # But the system knows C4 is the match.
            # If we scan relative to C3 (check_note_natural = note + 12), we might find C4.
            # Let's stick to scanning relative to the *played* note for Natural, 
            # checking if *those* notes have matches.
            check_note_natural = note + 12
        
        # Calculate Primary Gain
        if self.primary_lock:
            p_gain = 1.0
        else:
            p_gain = self.harmonic_mix
        target_gains.append(p_gain)
        
        # --- 3. Atmosphere (Spectral Folding) ---
        if self.multi_harmonic_enabled:
            # Secondary gain (controlled by Harmonic Mix)
            s_gain = 1.0 - self.harmonic_mix
            
            existing_freqs = {round(frequencies[0], 2)}
            
            # Use check_note_atmosphere for scanning
            check_note = check_note_atmosphere
            
            while len(frequencies) < self.max_harmonics + 1 and check_note <= 108: # +1 for primary
                # Get all matches in this octave
                octave_matches = self._key_mapper.get_all_matches(check_note)
                
                for m in octave_matches:
                    if len(frequencies) >= self.max_harmonics + 1:
                        break
                    
                    raw_freq = current_f1 * m.harmonic_n
                    
                    # Fold down to proximity of played note
                    # Calculate octave difference from PLAYED note
                    semitone_diff = check_note - note
                    fold_octaves = round(semitone_diff / 12)
                    folded_freq = raw_freq / (2 ** fold_octaves)
                    
                    if round(folded_freq, 2) not in existing_freqs:
                        frequencies.append(folded_freq)
                        harmonic_ns.append(m.harmonic_n)
                        target_gains.append(s_gain)
                        existing_freqs.add(round(folded_freq, 2))
                
                check_note += 12

        # --- 4. Natural Harmonics (Original Frequencies) ---
        if self.natural_harmonics_enabled:
            # Natural gain (controlled by CC92)
            n_gain = self.natural_harmonics_level / 127.0
            
            # Simple scan upwards from the played note
            # We look for direct matches in higher octaves
            check_note = check_note_natural
            
            # Safety limit: don't go crazy with voices
            max_natural_voices = 16 
            natural_count = 0
            
            while natural_count < max_natural_voices and check_note <= 108:
                # Check for match at this specific note
                nat_match = self._key_mapper.get_match(check_note)
                
                if nat_match:
                    freq = current_f1 * nat_match.harmonic_n
                    if freq <= 20000:
                        frequencies.append(freq)
                        harmonic_ns.append(nat_match.harmonic_n)
                        target_gains.append(n_gain)
                        natural_count += 1
                
                check_note += 12
        
        # --- 5. Voice Allocation & Setup ---
        
        # Set up LFO (only affects Primary/Atmosphere typically, or all?)
        # Logic applies "frequencies" to LFO. So it affects all.
        lfo = HarmonicLFO(rate=self.lfo_rate, mode=self.vibrato_mode)
        lfo.set_harmonics(frequencies)
        self._note_lfos[note] = lfo
        
        # Allocate voices
        vel_normalized = velocity / 127.0
        voice_ids = self.voices.note_on(
            note, velocity,
            frequencies=frequencies,
            harmonic_ns=harmonic_ns,
            original_f1=current_f1,
        )
            
        # --- 6. Send to OSC ---
        for i, voice_id in enumerate(voice_ids):
            freq = frequencies[i]
            n = harmonic_ns[i]
            gain_scale = target_gains[i]
            
            voice_vel = vel_normalized * gain_scale
            
            # Clamp for minimal activity if intended
            final_vel = max(0.001, voice_vel) if voice_vel > 0 else 0
            
            if final_vel > 0:
                self.osc.send_note_on(voice_id, freq, final_vel)
                self.osc.broadcast_voice_on(voice_id, freq, final_vel, note, n)
        
        # Broadcast key
        self.osc.broadcast_key_on(note, velocity)
        
        # --- 7. Send to MPE ---
        if self.mpe_enabled and self.mpe is not None:
            for i, voice_id in enumerate(voice_ids):
                gain_scale = target_gains[i]
                voice_vel = vel_normalized * gain_scale
                final_vel = max(0.001, voice_vel) if voice_vel > 0 else 0
                if final_vel > 0:
                    self.mpe.send_note_on(voice_id, frequencies[i], final_vel)
        
        if self.verbose:
            if match is not None:
                sign = '+' if match.deviation_cents >= 0 else ''
                print(f"♪ Note ON: MIDI {note} → n={primary_n} ({sign}{match.deviation_cents:.1f}¢)")
            else:
                print(f"♪ Note ON: MIDI {note} → n={primary_n} [borrowed]")
            
            # Summary of added layers
            atmos_count = len([g for g in target_gains[1:] if g == (1.0 - self.harmonic_mix)]) if self.multi_harmonic_enabled else 0
            nat_count = len([g for g in target_gains[1:] if g == (self.natural_harmonics_level/127.0)]) if self.natural_harmonics_enabled else 0
            
            if atmos_count > 0:
                print(f"    + {atmos_count} Atmosphere voices (Mix: {int((1.0-self.harmonic_mix)*100)}%)")
            if nat_count > 0:
                print(f"    + {nat_count} Natural voices (Level: {self.natural_harmonics_level})")

            
    def _handle_note_off(self, note: int, channel: int = 0) -> None:
        """Handle Note-Off event."""
        # Pad Mode Logic
        if self.pad_mode_enabled:
            # Map pad to harmonic
            layout = getattr(config, 'PAD_MAP_TYPE', 'LINEAR')
            n = 0
            is_upper_half = False
            
            if layout == 'LAUNCHPAD':
                rel = note - config.PAD_ANCHOR_NOTE
                if rel >= 0:
                    x = rel % 16
                    y = rel // 16
                    if x < 8 and y < 8:
                        # Invert Y so harmonic 1 is at Bottom-Left
                        row_from_bottom = 7 - y
                        if self.split_mode_enabled:
                            if row_from_bottom < 4:
                                n = 1 + x + (row_from_bottom * 8)
                            else:
                                n = 1 + x + ((row_from_bottom - 4) * 8)
                                is_upper_half = True
                        else:
                             n = 1 + x + (row_from_bottom * 8)
            else:
                n = 1 + (note - config.PAD_ANCHOR_NOTE)
            
            # If Split Mode Upper Half (Latching), IGNORE Note Off
            if is_upper_half:
                return

            # If it was a valid harmonic pad, turn off its voice
            if 1 <= n <= 64:
                # Turn off pad light (Mirror channel) - ONLY if not latched
                self.midi.send_message(mido.Message('note_off', note=note, velocity=0, channel=channel))
                
                pair = self.voices.note_off(note)
                if pair is None:
                    return # No voice was active for this note
                
                # Clean up LFO for this note
                self._note_lfos.pop(note, None)
                
                # === Send to OSC ===
                for i, voice_id in enumerate(pair.voice_ids):
                    freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
                    self.osc.send_note_off(voice_id, frequency=freq)
                    self.osc.broadcast_voice_off(voice_id)
                
                # Broadcast key off
                self.osc.broadcast_key_off(note)
                
                # === Send to MPE ===
                if self.mpe_enabled and self.mpe is not None:
                    for i, voice_id in enumerate(pair.voice_ids):
                        freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
                        self.mpe.send_note_off(voice_id, frequency=freq)
                
                if self.verbose:
                    print(f"♫ Pad OFF: MIDI {note} ({len(pair.voice_ids)} voices)")
            return # Handled pad mode note off
        
        # Keyboard Mode Logic
        pair = self.voices.note_off(note)
        if pair is None:
            return
        
        # Clean up LFO for this note
        self._note_lfos.pop(note, None)
        
        # === Send to OSC ===
        for i, voice_id in enumerate(pair.voice_ids):
            freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
            self.osc.send_note_off(voice_id, frequency=freq)
            self.osc.broadcast_voice_off(voice_id)
        
        # Broadcast key off
        self.osc.broadcast_key_off(note)
        
        # === Send to MPE ===
        if self.mpe_enabled and self.mpe is not None:
            for i, voice_id in enumerate(pair.voice_ids):
                freq = pair.frequencies[i] if i < len(pair.frequencies) else 0.0
                self.mpe.send_note_off(voice_id, frequency=freq)
        
        if self.verbose:
            print(f"♫ Note OFF: MIDI {note} ({len(pair.voice_ids)} voices)")
            
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
            # Iterate through all voices for this note
            for i, voice_id in enumerate(pair.voice_ids):
                if i >= len(pair.frequencies) or i >= len(pair.harmonic_ns):
                    continue
                    
                original_freq = pair.frequencies[i]
                harmonic_n = pair.harmonic_ns[i]
                
                # Calculate new frequency based on current f₁
                new_freq = current_f1 * harmonic_n
                
                # Calculate semitone offset from original frequency
                original_midi = frequency_to_midi_float(original_freq)
                new_midi = frequency_to_midi_float(new_freq)
                semitone_offset = new_midi - original_midi
                
                # === Send to OSC ===
                self.osc.send_pitch_expression(voice_id, semitone_offset)
                
                # === Send to MPE ===
                if self.mpe_enabled and self.mpe is not None:
                    self.mpe.send_pitch_expression(voice_id, semitone_offset)
    
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
        
        # Update all active voices with new frequencies
        self._update_active_voices()
        
        # Broadcast new f1 and anchor to visualizer
        self.osc.broadcast_f1(new_f1)
        self.osc.broadcast_anchor(new_anchor)
        
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
    
    def _handle_multi_harmonic_toggle(self, cc_value: int) -> None:
        """Handle multi-harmonic mode toggle (CC29).
        
        When enabled, plays the same interval at multiple octaves.
        
        Args:
            cc_value: CC value (0=single voice, >=64=multi-harmonic)
        """
        enabled = cc_value >= 64
        if enabled != self.multi_harmonic_enabled:
            self.multi_harmonic_enabled = enabled
            if self.verbose:
                state = "ON ✓" if enabled else "OFF ✗"
                print(f"🎹 Multi-Harmonic: {state}")
    
    def _handle_max_harmonics_change(self, cc_value: int) -> None:
        """Handle max harmonics CC (CC90).
        
        Sets how many octave harmonics to play in multi-harmonic mode.
        
        Args:
            cc_value: CC value (0-127) maps to 1-4 harmonics
        """
        # Map 0-127 to 1-4 harmonics
        self.max_harmonics = 1 + int(cc_value / 127.0 * 3)
        if self.verbose:
            print(f"🎚️ Max Harmonics: {self.max_harmonics}")

    def _handle_primary_lock_toggle(self, cc_value: int) -> None:
        """Handle primary voice lock toggle (CC28).
        
        Args:
            cc_value: CC value (>=64 is ON)
        """
        enabled = cc_value >= 64
        if enabled != self.primary_lock:
            self.primary_lock = enabled
            if self.verbose:
                state = "LOCKED 🔒" if enabled else "UNLOCKED 🔓"
                print(f"⚓ Primary Voice: {state}")
    
    def _handle_harmonic_mix_change(self, cc_value: int) -> None:
        """Handle harmonic mix slider (CC89).
        
        Controls balance between Primary (fundamental) and Additional Harmonics.
        0 (Bottom) = Harmonics Focused
        127 (Top) = Primary Focused
        
        Args:
            cc_value: CC value (0-127)
        """
        self.harmonic_mix = cc_value / 127.0
        if self.verbose:
            mix_pct = int(self.harmonic_mix * 100)
            print(f"🎚️ Harmonic Mix: {mix_pct}%")
            
    def _handle_natural_harmonics_toggle(self, cc_value: int) -> None:
        """Handle Natural Harmonics Mode toggle (CC30).
        
        Args:
            cc_value: CC value (>=64 is ON)
        """
        enabled = cc_value >= 64
        if enabled != self.natural_harmonics_enabled:
            self.natural_harmonics_enabled = enabled
            if self.verbose:
                state = "ON ✓" if enabled else "OFF ✗"
                print(f"🎹 Natural Harmonics: {state}")
                
    def _handle_natural_level_change(self, cc_value: int) -> None:
        """Handle Natural Harmonics Level slider (CC92).
        
        Args:
            cc_value: CC value (0-127)
        """
        self.natural_harmonics_level = cc_value
        if self.verbose:
            print(f"🎚️ Natural Level: {cc_value}")

    
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
                        self._handle_note_on(msg.note, msg.velocity, msg.channel)
                        
                    elif self.midi.is_note_off(msg):
                        self._handle_note_off(msg.note, msg.channel)
                        
                    elif self.midi.is_f1_control(msg):
                        self._handle_f1_change(msg.value)
                    
                    elif self.midi.is_tolerance_control(msg):
                        self._handle_tolerance_change(msg.value)
                    
                    elif self.midi.is_lfo_rate_control(msg):
                        self._handle_lfo_rate_change(msg.value)
                    
                    elif self.midi.is_vibrato_mode_toggle(msg):
                        self._handle_vibrato_mode_toggle(msg.value)
                    
                    elif self.midi.is_multi_harmonic_toggle(msg):
                        self._handle_multi_harmonic_toggle(msg.value)
                    
                    elif self.midi.is_max_harmonics_control(msg):
                        self._handle_max_harmonics_change(msg.value)
                        
                    elif self.midi.is_primary_lock_toggle(msg):
                        self._handle_primary_lock_toggle(msg.value)
                        
                    elif self.midi.is_harmonic_mix_control(msg):
                        self._handle_harmonic_mix_change(msg.value)
                        
                    elif self.midi.is_natural_harmonics_toggle(msg):
                        self._handle_natural_harmonics_toggle(msg.value)
                        
                    elif self.midi.is_natural_level_control(msg):
                        self._handle_natural_level_change(msg.value)

                    elif self.midi.is_panic_cc(msg) and msg.value > 0:
                        self.panic()

                    elif self.midi.is_split_mode_toggle(msg):
                        self._handle_split_mode_toggle(msg.value)

                
                # Poll secondary controller for modulation notes
                if self.secondary_midi is not None:
                    for msg in self.secondary_midi.poll():
                        if self.secondary_midi.is_note_on(msg):
                            # Modulation note - change anchor without producing sound
                            self._handle_modulation_note(msg.note)
                        
                        elif self.secondary_midi.is_f1_control(msg):
                            self._handle_f1_change(msg.value)
                            
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
    parser.add_argument(
        "--midi-debug",
        action="store_true",
        help="Enable detailed MIDI input/output logging",
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
        midi_debug=args.midi_debug,
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
