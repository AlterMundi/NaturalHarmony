"""OSC receiver for visualizer.

Listens to broadcasts from Harmonic Beacon and updates state.
"""

import threading
from typing import Optional

try:
    import pyliblo3 as liblo
    HAS_LIBLO = True
except ImportError:
    HAS_LIBLO = False
    liblo = None  # type: ignore

from . import config
from .state import VisualizerState


class OscReceiver:
    """Receives OSC messages from Harmonic Beacon.
    
    Runs in a background thread, updating shared state.
    """
    
    def __init__(self, state: VisualizerState, port: int = config.OSC_PORT):
        """Initialize the receiver.
        
        Args:
            state: Shared state object to update
            port: UDP port to listen on
        """
        if not HAS_LIBLO:
            raise ImportError(
                "pyliblo3 is required for OSC communication. "
                "Install with: pip install pyliblo3"
            )
        
        self.state = state
        self.port = port
        self._server: Optional[liblo.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start the OSC receiver in a background thread."""
        self._server = liblo.Server(self.port)
        
        # Register handlers for all beacon messages
        self._server.add_method("/beacon/f1", "f", self._handle_f1)
        self._server.add_method("/beacon/anchor", "i", self._handle_anchor)
        self._server.add_method("/beacon/voice/on", "iffi", self._handle_voice_on)
        self._server.add_method("/beacon/voice/off", "i", self._handle_voice_off)
        self._server.add_method("/beacon/voice/freq", "if", self._handle_voice_freq)
        self._server.add_method("/beacon/key/on", "ii", self._handle_key_on)
        self._server.add_method("/beacon/key/off", "i", self._handle_key_off)
        self._server.add_method("/beacon/cc", "ii", self._handle_cc)
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the OSC receiver."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._server = None
    
    def _run(self) -> None:
        """Background thread main loop."""
        while self._running and self._server:
            # Receive with 10ms timeout for responsive shutdown
            self._server.recv(10)
    
    def _handle_f1(self, path: str, args: list) -> None:
        """Handle /beacon/f1 message."""
        self.state.f1 = args[0]
    
    def _handle_anchor(self, path: str, args: list) -> None:
        """Handle /beacon/anchor message."""
        self.state.anchor_note = args[0]
    
    def _handle_voice_on(self, path: str, args: list) -> None:
        """Handle /beacon/voice/on message."""
        try:
            # Try parsing with new 5-argument format
            voice_id, freq, gain, source_note, harmonic_n = args
        except ValueError:
            # Fallback for old format (4 arguments)
            voice_id, freq, gain, source_note = args
            harmonic_n = 1
            
        self.state.voice_on(voice_id, freq, gain, source_note, harmonic_n)
    
    def _handle_voice_off(self, path: str, args: list) -> None:
        """Handle /beacon/voice/off message."""
        self.state.voice_off(args[0])
    
    def _handle_voice_freq(self, path: str, args: list) -> None:
        """Handle /beacon/voice/freq message."""
        voice_id, freq = args
        self.state.voice_freq(voice_id, freq)
    
    def _handle_key_on(self, path: str, args: list) -> None:
        """Handle /beacon/key/on message."""
        note, velocity = args
        self.state.key_on(note, velocity)
    
    def _handle_key_off(self, path: str, args: list) -> None:
        """Handle /beacon/key/off message."""
        self.state.key_off(args[0])
    
    def _handle_cc(self, path: str, args: list) -> None:
        """Handle /beacon/cc message."""
        cc_num, value = args
        self.state.update_cc(cc_num, value)
