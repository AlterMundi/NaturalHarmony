"""OSC receiver for visualizer.

Listens to broadcasts from Harmonic Beacon and updates state.
"""

import threading
from typing import Optional

try:
    from pythonosc import dispatcher
    from pythonosc import osc_server
    HAS_OSC = True
except ImportError:
    HAS_OSC = False
    dispatcher = None  # type: ignore
    osc_server = None  # type: ignore

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
        if not HAS_OSC:
            raise ImportError(
                "python-osc is required for OSC communication. "
                "Install with: pip install python-osc"
            )
        
        self.state = state
        self.port = port
        self._server: Optional[osc_server.ThreadingOSCUDPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start the OSC receiver in a background thread."""
        if not HAS_OSC:
            return

        disp = dispatcher.Dispatcher()
        
        # Register handlers for all beacon messages
        # python-osc handlers receive: (address, *args)
        disp.map("/beacon/f1", self._handle_f1)
        disp.map("/beacon/anchor", self._handle_anchor)
        disp.map("/beacon/voice/on", self._handle_voice_on)
        disp.map("/beacon/voice/off", self._handle_voice_off)
        disp.map("/beacon/voice/freq", self._handle_voice_freq)
        disp.map("/beacon/key/on", self._handle_key_on)
        disp.map("/beacon/key/off", self._handle_key_off)
        disp.map("/beacon/cc", self._handle_cc)
        disp.map("/beacon/mode/pad", self._handle_pad_mode)
        
        self._server = osc_server.ThreadingOSCUDPServer(
            ("0.0.0.0", self.port), 
            disp
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the OSC receiver."""
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        
        if self._thread:
            self._thread.join(timeout=1.0)
        self._server = None
    
    def _run(self) -> None:
        """Background thread main loop."""
        if self._server:
            self._server.serve_forever()
    
    def _handle_f1(self, address: str, *args) -> None:
        """Handle /beacon/f1 message."""
        if args:
            self.state.f1 = args[0]
    
    def _handle_anchor(self, address: str, *args) -> None:
        """Handle /beacon/anchor message."""
        if args:
            self.state.anchor_note = args[0]
    
    def _handle_voice_on(self, address: str, *args) -> None:
        """Handle /beacon/voice/on message."""
        try:
            # Try parsing with new 5-argument format
            if len(args) >= 5:
                voice_id, freq, gain, source_note, harmonic_n = args[:5]
            elif len(args) == 4:
                # Fallback for old format (4 arguments)
                voice_id, freq, gain, source_note = args
                harmonic_n = 1
            else:
                return
            
            self.state.voice_on(voice_id, freq, gain, source_note, harmonic_n)
        except ValueError:
            pass
    
    def _handle_voice_off(self, address: str, *args) -> None:
        """Handle /beacon/voice/off message."""
        if args:
            self.state.voice_off(int(args[0]))
    
    def _handle_voice_freq(self, address: str, *args) -> None:
        """Handle /beacon/voice/freq message."""
        if len(args) >= 2:
            voice_id, freq = args[:2]
            self.state.voice_freq(voice_id, freq)
    
    def _handle_key_on(self, address: str, *args) -> None:
        """Handle /beacon/key/on message."""
        try:
            if len(args) >= 2:
                note, velocity = args[:2]
                self.state.key_on(note, velocity)
        except ValueError:
            pass
    
    def _handle_key_off(self, address: str, *args) -> None:
        """Handle /beacon/key/off message."""
        try:
            if args:
                note = args[0]
                self.state.key_off(note)
        except (ValueError, IndexError):
            pass
    
    def _handle_cc(self, address: str, *args) -> None:
        """Handle /beacon/cc message."""
        if len(args) >= 2:
            cc_num, value = args[:2]
            self.state.update_cc(cc_num, value)

    def _handle_pad_mode(self, address: str, *args) -> None:
        """Handle /beacon/mode/pad message."""
        if args:
            enabled = bool(args[0])
            self.state.pad_mode_enabled = enabled
            print(f"Visualizer: Switched to Pad Mode: {enabled}")

