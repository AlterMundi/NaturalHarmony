"""Main entry point for The Harmonic Beacon.

Orchestrates MIDI input, harmonic calculation, and OSC output
in a real-time event loop.
"""

import argparse
import signal
import sys
import time
from typing import Optional

from . import config
from .harmonics import (
    beacon_frequency,
    get_harmonic_for_key,
    playable_frequency,
    frequency_to_midi_float,
)
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
        verbose: bool = True,
    ):
        """Initialize The Harmonic Beacon.
        
        Args:
            mock_osc: If True, use MockOscSender instead of real OSC
            verbose: If True, print status messages
        """
        self.verbose = verbose
        self.running = False
        
        # Initialize components
        self.midi = MidiHandler()
        self.osc: OscSender = MockOscSender(verbose=verbose) if mock_osc else OscSender()
        self.voices = VoiceTracker()
        self.f1 = F1Modulator()
        
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
        """Handle a Note-On event."""
        # Calculate harmonic dynamically based on key position
        n = get_harmonic_for_key(note, config.ANCHOR_MIDI_NOTE)
        
        # Calculate frequencies
        current_f1 = self.f1.value
        beacon_freq = beacon_frequency(current_f1, n)
        playable_freq = playable_frequency(
            current_f1, n, config.PLAYABLE_TARGET_OCTAVE
        )
        
        # Allocate voices (store frequencies and f1 for pitch sliding)
        beacon_id, playable_id = self.voices.note_on(
            note, velocity, 
            beacon_freq=beacon_freq, 
            playable_freq=playable_freq,
            original_f1=current_f1,
            harmonic_n=n,
        )
        vel_normalized = velocity / 127.0
        
        self.osc.send_note_on(beacon_id, beacon_freq, vel_normalized)
        self.osc.send_note_on(playable_id, playable_freq, vel_normalized)
        
        if self.verbose:
            print(f"♪ Note ON: MIDI {note} → n={n}")
            print(f"    Beacon:   {beacon_freq:.2f} Hz")
            print(f"    Playable: {playable_freq:.2f} Hz")
            
    def _handle_note_off(self, note: int) -> None:
        """Handle a Note-Off event."""
        pair = self.voices.note_off(note)
        if pair is None:
            return
        
        # Send note-off with frequencies (required by Surge XT)
        self.osc.send_note_off(
            pair.beacon_voice_id, 
            frequency=pair.beacon_frequency
        )
        self.osc.send_note_off(
            pair.playable_voice_id,
            frequency=pair.playable_frequency
        )
        
        if self.verbose:
            print(f"♫ Note OFF: MIDI {note}")
            
    def _handle_f1_change(self, cc_value: int) -> None:
        """Handle f₁ modulation CC."""
        self.f1.set_target_from_cc(cc_value)
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
                current_f1, pair.harmonic_n, config.PLAYABLE_TARGET_OCTAVE
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
        """Handle channel aftertouch to set new f₁ center.
        
        When aftertouch is triggered, the last played note's beacon frequency
        becomes the new f₁ (recentering the harmonic series so that note = n=1).
        This does NOT slide existing notes - it sets up for future notes.
        
        Args:
            value: Aftertouch pressure value (0-127)
        """
        # Only trigger on significant pressure (threshold avoids accidental triggers)
        if value < 64:
            return
        
        pair = self.voices.get_last_played_pair()
        if pair is None:
            return
        
        # The last played note's beacon frequency becomes the new f₁
        # This recenters the series so that note becomes the fundamental
        new_f1 = pair.beacon_frequency
        
        # Transpose to allowed range (preserve pitch class)
        # If too low, shift up octaves
        while new_f1 < self.f1.min_freq:
            new_f1 *= 2.0
            
        # If too high, shift down octaves
        while new_f1 > self.f1.max_freq:
            new_f1 /= 2.0
        
        # Set as target (no sliding for aftertouch - instant set)
        self.f1.value = new_f1
        self.f1.target = new_f1
        
        if self.verbose:
            print(f"⚓ Aftertouch center: f₁ = {new_f1:.1f} Hz (from MIDI {pair.midi_note})")
            
    def run(self) -> None:
        """Run the main event loop."""
        self.start()
        
        try:
            while self.running:
                # Update f₁ interpolation
                f1_changed = self.f1.update()
                
                # If f₁ changed, update all active voices
                if f1_changed and self.voices.active_count > 0:
                    self._update_active_voices()
                
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
