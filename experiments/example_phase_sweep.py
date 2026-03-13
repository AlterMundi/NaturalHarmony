"""Example: sweep harmonic 2's phase from 0° to 360° over a set duration."""

import math
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from experiments.base import Experiment


class PhaseSweep(Experiment):
    """Slowly rotate the phase of a target harmonic from 0° to 360°.

    This changes the interference pattern between harmonics, visibly
    deforming the cymatic laser pattern on the wall.
    """

    name = "phase_sweep"
    description = "Sweep one harmonic's phase 0→360° and back while others are static."

    def __init__(
        self,
        target_harmonic: int = 2,
        duration_s: float = 30.0,
        cycles: int = 1,
        base_url: str = "http://127.0.0.1:8080",
    ):
        super().__init__(base_url)
        self.target = target_harmonic
        self.duration = duration_s
        self.cycles = cycles

    def run(self):
        step_s = 0.05   # 20 Hz updates
        total_steps = int(self.duration / step_s)

        print(f"[phase_sweep] H{self.target}: 0° → 360° × {self.cycles} over {self.duration}s")

        for i in range(total_steps):
            t = i / total_steps            # 0.0 to 1.0
            phase_deg = (t * 360 * self.cycles) % 360
            self.client.set_phase(self.target, phase_deg)
            time.sleep(step_s)

        # Return to 0°
        self.client.set_phase(self.target, 0.0)
        print("[phase_sweep] Done — phase reset to 0°")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Phase sweep experiment")
    p.add_argument("--harmonic", type=int, default=2, help="Harmonic to sweep")
    p.add_argument("--duration", type=float, default=30.0, help="Duration in seconds")
    p.add_argument("--cycles", type=int, default=1, help="Number of full rotations")
    p.add_argument("--no-record", action="store_true", help="Skip dataset recording")
    args = p.parse_args()

    exp = PhaseSweep(
        target_harmonic=args.harmonic,
        duration_s=args.duration,
        cycles=args.cycles,
    )
    exp.execute(record=not args.no_record)
