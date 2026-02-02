"""Main entry point for the Harmonic Visualizer."""

import argparse
import signal
import sys

from . import config
from .state import VisualizerState
from .osc_receiver import OscReceiver


def main() -> None:
    """Entry point for the Harmonic Visualizer CLI."""
    parser = argparse.ArgumentParser(
        description="Harmonic Visualizer - Real-time harmonic series display"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.OSC_PORT,
        help=f"OSC port to listen on (default: {config.OSC_PORT})",
    )
    parser.add_argument(
        "--no-lines",
        action="store_true",
        help="Disable energy lines (can toggle with 'E' key)",
    )
    parser.add_argument(
        "--3d",
        dest="use_3d",
        action="store_true",
        help="Use 3D renderer with bloom effects",
    )
    
    args = parser.parse_args()
    
    # Create shared state
    state = VisualizerState()
    
    # Create components
    receiver = OscReceiver(state, port=args.port)
    
    # Choose renderer
    if args.use_3d:
        from .renderer_3d import Renderer3D
        renderer = Renderer3D(state)
        mode_str = "3D"
    else:
        from .renderer import Renderer
        renderer = Renderer(state)
        mode_str = "2D"
    
    if args.no_lines:
        renderer.show_energy_lines = False
    
    # Handle signals
    def signal_handler(sig, frame):
        renderer.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start
    print(f"Harmonic Visualizer starting ({mode_str})...")
    print(f"  Listening on OSC port {args.port}")
    print(f"  Press 'E' to toggle energy lines")
    if args.use_3d:
        print(f"  Arrow keys to orbit camera")
    print(f"  Press ESC to quit")
    
    try:
        receiver.start()
        renderer.start()
        
        # Main loop
        while renderer.running:
            dt = renderer.clock.tick(config.FPS) / 1000.0
            
            if not renderer.handle_events():
                break
            
            renderer.render(dt)
            
    except KeyboardInterrupt:
        pass
    finally:
        renderer.stop()
        receiver.stop()
        print("Visualizer stopped.")


if __name__ == "__main__":
    main()
