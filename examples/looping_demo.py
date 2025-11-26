#!/usr/bin/env python3
"""
Example: Looping and graceful stop.

This example demonstrates:
1. Starting a looping sound
2. Playing it for a while
3. Setting looping to false for a graceful stop (lets current iteration finish)

WARNING: This will play audio!
"""

import time
from fa_launcher_audio import AudioManager


def data_provider(name: str) -> bytes:
    """Not used in this example."""
    raise FileNotFoundError(f"No files: {name}")


def main():
    print("Looping demo - demonstrating graceful stop")
    print("=" * 50)

    with AudioManager(data_provider=data_provider) as mgr:
        # Create a short beep that loops
        # Using a short duration so loops are noticeable
        beep_duration = 0.3

        print(f"\n1. Starting looping beep (duration per loop: {beep_duration}s)")
        mgr.submit_command({
            "command": "patch",
            "id": "looping_beep",
            "source": {
                "kind": "waveform",
                "waveform": "sine",
                "frequency": 880,  # A5 note
                "non_looping_duration": beep_duration,
            },
            "volume": 0.25,
            "looping": True,
            "playback_rate": 1.0,
        })

        # Let it loop for a bit
        print("   Playing looped sound for 2 seconds...")
        time.sleep(2.0)

        print("\n2. Setting looping=false for graceful stop")
        print("   (Sound will finish current iteration then stop)")
        mgr.submit_command({
            "command": "patch",
            "id": "looping_beep",
            "source": {
                "kind": "waveform",
                "waveform": "sine",
                "frequency": 880,
                "non_looping_duration": beep_duration,
            },
            "volume": 0.25,
            "looping": False,  # Changed to false
            "playback_rate": 1.0,
        })

        # Wait for it to finish gracefully
        print("   Waiting for graceful stop...")
        time.sleep(beep_duration + 0.2)

        print("\n3. Now demonstrating immediate stop with 'stop' command")
        print("   Starting another looping sound...")

        mgr.submit_command({
            "command": "patch",
            "id": "looping_beep_2",
            "source": {
                "kind": "waveform",
                "waveform": "square",
                "frequency": 440,  # A4 note
                "non_looping_duration": 0.5,
            },
            "volume": 0.2,
            "looping": True,
            "playback_rate": 1.0,
        })

        time.sleep(1.5)

        print("   Sending 'stop' command (immediate stop)...")
        mgr.submit_command({
            "command": "stop",
            "id": "looping_beep_2",
        })

        time.sleep(0.1)
        print("\nDone!")


if __name__ == "__main__":
    main()
