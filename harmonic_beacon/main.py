"""Main entry point for The Harmonic Beacon.

Orchestrates MIDI input, harmonic calculation, and OSC output
in a real-time event loop.
"""

import argparse
from enum import Enum
import signal
import sys
import time
from typing import Optional


class AftertouchMode(Enum):
    """Aftertouch behavior modes."""
    F1_CENTER = 0   # CC22 OFF: Aftertouch sets f₁, anchor stays at C1
    KEY_ANCHOR = 1  # CC22 ON: Aftertouch sets f₁ AND moves anchor to pressed key

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
        verbose: bool = True,
    ):
        """Initialize The Harmonic Beacon.
        
        Args:
            mock_osc: If True, use MockOscSender instead of real OSC
            broadcast: If True, broadcast state to visualizer
            verbose: If True, print status messages
        """
        self.verbose = verbose
        self.running = False
        
        # Aftertouch mode (toggled by CC22)
        self.aftertouch_mode = AftertouchMode.F1_CENTER
        
        # Tolerance and LFO settings
        self.tolerance = config.DEFAULT_TOLERANCE
        self.lfo_rate = config.DEFAULT_LFO_RATE
        self.vibrato_mode = VibratoMode.SMOOTH
        
        # Aftertouch settings
        self.aftertouch_enabled = True  # Can be toggled off with CC30
        self.aftertouch_threshold = config.DEFAULT_AFTERTOUCH_THRESHOLD
        
        # Per-note LFOs for harmonic chorus
        self._note_lfos: dict[int, HarmonicLFO] = {}
        self._last_update_time = time.time()
        
        # Initialize components
        self.midi = MidiHandler()
        self.osc: OscSender = MockOscSender(verbose=verbose) if mock_osc else OscSender(broadcast=broadcast)
        self.voices = VoiceTracker()
        self.f1 = F1Modulator()
        
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
        # Open MIDI port
        port_name = self.midi.open()
        if self.verbose:
            print(f"✓ MIDI: Connected to '{port_name}'")
            
        # Open OSC connection
        self.osc.open()
        if self.verbose:
            print(f"✓ OSC: Targeting {self.osc.host}:{self.osc.port}")
            print(f"✓ f₁: {self.f1.value:.1f} Hz (range: {self.f1.min_freq}-{self.f1.max_freq} Hz)")
            print("\n🎵 The Harmonic Beacon is active! Press Ctrl+C to stop.\n")
        
        self.running = True
        
    def stop(self) -> None:
        """Stop the Harmonic Beacon and release all resources."""
        self.running = False
        
        # Release all active voices
        self.osc.send_all_notes_off()
        self.voices.clear()
            
        # Close connections
        self.midi.close()
        self.osc.close()
        
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
        else:
            primary_n = borrowed.harmonic_n
            beacon_freq = current_f1 * primary_n  # Use current f1, not stored
        
        playable_freq = playable_frequency(current_f1, primary_n, note)
        
        # Set up LFO (single harmonic, no chorus needed)
        lfo = HarmonicLFO(rate=self.lfo_rate, mode=self.vibrato_mode)
        lfo.set_harmonics([beacon_freq])
        self._note_lfos[note] = lfo
        
        # Allocate voices
        beacon_id, playable_id = self.voices.note_on(
            note, velocity, 
            beacon_freq=beacon_freq, 
            playable_freq=playable_freq,
            original_f1=current_f1,
            harmonic_n=primary_n,
        )
        vel_normalized = velocity / 127.0
        
        self.osc.send_note_on(beacon_id, beacon_freq, vel_normalized)
        self.osc.send_note_on(playable_id, playable_freq, vel_normalized)
        
        # Broadcast to visualizer
        self.osc.broadcast_key_on(note, velocity)
        self.osc.broadcast_voice_on(beacon_id, beacon_freq, vel_normalized, note, primary_n)
        self.osc.broadcast_voice_on(playable_id, playable_freq, vel_normalized, note, primary_n)
        
        if self.verbose:
            if match is not None:
                sign = '+' if match.deviation_cents >= 0 else ''
                print(f"♪ Note ON: MIDI {note} → n={primary_n} ({sign}{match.deviation_cents:.1f}¢)")
            else:
                print(f"♪ Note ON: MIDI {note} → n={primary_n} [borrowed from MIDI {borrowed.borrowed_midi}]")
            print(f"    Beacon:   {beacon_freq:.2f} Hz")
            print(f"    Playable: {playable_freq:.2f} Hz")
            
    def _handle_note_off(self, note: int) -> None:
        """Handle a Note-Off event."""
        pair = self.voices.note_off(note)
        if pair is None:
            return
        
        # Clean up LFO for this note
        self._note_lfos.pop(note, None)
        
        # Send note-off with frequencies (required by Surge XT)
        self.osc.send_note_off(
            pair.beacon_voice_id, 
            frequency=pair.beacon_frequency
        )
        self.osc.send_note_off(
            pair.playable_voice_id,
            frequency=pair.playable_frequency
        )
        
        # Broadcast to visualizer
        self.osc.broadcast_key_off(note)
        self.osc.broadcast_voice_off(pair.beacon_voice_id)
        self.osc.broadcast_voice_off(pair.playable_voice_id)
        
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
            # Calculate new frequencies based on current f₁
            new_beacon_freq = beacon_frequency(current_f1, pair.harmonic_n)
            new_playable_freq = playable_frequency(
                current_f1, pair.harmonic_n, note
            )
            
            # Calculate semitone offsets from original frequencies
            original_beacon_midi = frequency_to_midi_float(pair.beacon_frequency)
            new_beacon_midi = frequency_to_midi_float(new_beacon_freq)
            beacon_semitone_offset = new_beacon_midi - original_beacon_midi
            
            original_playable_midi = frequency_to_midi_float(pair.playable_frequency)
            new_playable_midi = frequency_to_midi_float(new_playable_freq)
            playable_semitone_offset = new_playable_midi - original_playable_midi
            
            # Send pitch expressions to Surge XT
            self.osc.send_pitch_expression(pair.beacon_voice_id, beacon_semitone_offset)
            self.osc.send_pitch_expression(pair.playable_voice_id, playable_semitone_offset)
    
    def _handle_aftertouch(self, value: int) -> None:
        """Handle channel aftertouch based on current mode.
        
        F1_CENTER mode (CC22 OFF):
            Sets f₁ to the last played note's beacon frequency.
            Anchor stays at C1 (config.ANCHOR_MIDI_NOTE).
            
        KEY_ANCHOR mode (CC22 ON):
            Sets f₁ AND moves the anchor to the last played key.
            That key becomes n=1 (the fundamental).
        
        Args:
            value: Aftertouch pressure value (0-127)
        """
        # Check if aftertouch is enabled
        if not self.aftertouch_enabled:
            return
        
        # Only trigger when pressure exceeds threshold
        if value < self.aftertouch_threshold:
            return
        
        pair = self.voices.get_last_played_pair()
        if pair is None:
            return
        
        # The last played note's beacon frequency becomes the new f₁
        new_f1 = pair.beacon_frequency
        
        # Transpose to allowed range (preserve pitch class)
        while new_f1 < self.f1.min_freq:
            new_f1 *= 2.0
        while new_f1 > self.f1.max_freq:
            new_f1 /= 2.0
        
        # Set f₁ instantly (no sliding for aftertouch)
        self.f1.value = new_f1
        self.f1.target = new_f1
        
        # In KEY_ANCHOR mode, also move the anchor to the pressed key
        if self.aftertouch_mode == AftertouchMode.KEY_ANCHOR:
            config.ANCHOR_MIDI_NOTE = pair.midi_note
            if self.verbose:
                print(f"⚓ Key Anchor: MIDI {pair.midi_note} is now n=1, f₁ = {new_f1:.1f} Hz")
        else:
            if self.verbose:
                print(f"⚓ f₁ Center: f₁ = {new_f1:.1f} Hz (from MIDI {pair.midi_note})")
    
    def _handle_mode_toggle(self, cc_value: int) -> None:
        """Handle aftertouch mode toggle (CC22).
        
        Args:
            cc_value: CC value (0=OFF, 127=ON for toggle buttons)
        """
        new_mode = AftertouchMode.KEY_ANCHOR if cc_value >= 64 else AftertouchMode.F1_CENTER
        
        if new_mode != self.aftertouch_mode:
            self.aftertouch_mode = new_mode
            if self.verbose:
                mode_name = "Key Anchor 🎯" if new_mode == AftertouchMode.KEY_ANCHOR else "f₁ Center 📍"
                print(f"🔄 Mode: {mode_name}")
    
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
    
    def _handle_aftertouch_enable_toggle(self, cc_value: int) -> None:
        """Handle aftertouch enable toggle (CC30).
        
        Args:
            cc_value: CC value (0=disabled, 127=enabled)
        """
        enabled = cc_value >= 64
        if enabled != self.aftertouch_enabled:
            self.aftertouch_enabled = enabled
            if self.verbose:
                state = "ON ✓" if enabled else "OFF ✗"
                print(f"👆 Aftertouch: {state}")
    
    def _handle_aftertouch_threshold_change(self, cc_value: int) -> None:
        """Handle aftertouch threshold CC (CC92).
        
        Args:
            cc_value: CC value (0-127) used directly as threshold
        """
        self.aftertouch_threshold = cc_value
        if self.verbose:
            print(f"🎚️ Aftertouch threshold: {cc_value}")
    
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
                    
                    elif self.midi.is_aftertouch(msg):
                        self._handle_aftertouch(msg.value)
                    
                    elif self.midi.is_mode_toggle(msg):
                        self._handle_mode_toggle(msg.value)
                    
                    elif self.midi.is_tolerance_control(msg):
                        self._handle_tolerance_change(msg.value)
                    
                    elif self.midi.is_lfo_rate_control(msg):
                        self._handle_lfo_rate_change(msg.value)
                    
                    elif self.midi.is_vibrato_mode_toggle(msg):
                        self._handle_vibrato_mode_toggle(msg.value)
                    
                    elif self.midi.is_aftertouch_enable_toggle(msg):
                        self._handle_aftertouch_enable_toggle(msg.value)
                    
                    elif self.midi.is_aftertouch_threshold_control(msg):
                        self._handle_aftertouch_threshold_change(msg.value)
                
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
    
    # Create and run the beacon
    beacon = HarmonicBeacon(
        mock_osc=args.mock,
        broadcast=args.broadcast,
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
