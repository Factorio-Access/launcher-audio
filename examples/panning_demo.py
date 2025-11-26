#!/usr/bin/env python3
"""
Example: Panning demo.

This example demonstrates changing pan over time using time-based parameters.
The sound will pan from left to right over 3 seconds.

WARNING: This will play audio!
"""

import time
from fa_launcher_audio import AudioManager


def data_provider(name: str) -> bytes:
    """Not used in this example."""
    raise FileNotFoundError(f"No files: {name}")


def main():
    print("Playing sine wave with pan from left to right...")
    print("(Press Ctrl+C to stop)")

    with AudioManager(data_provider=data_provider) as mgr:
        # Play a sine wave that pans from left to right
        mgr.submit_command({
            "command": "patch",
            "id": "panning_sound",
            "source": {
                "kind": "waveform",
                "waveform": "sine",
                "frequency": 440,  # A4 note
                "non_looping_duration": 3.0,
            },
            "volume": 0.3,  # Lower volume
            # Pan from left (-1) to right (+1)
            "pan": [
                {"time": 0.0, "value": -1.0, "interpolation_from_prev": "linear"},
                {"time": 3.0, "value": 1.0, "interpolation_from_prev": "linear"},
            ],
            "looping": False,
            "playback_rate": 1.0,
        })

        try:
            time.sleep(4)
        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
