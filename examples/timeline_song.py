#!/usr/bin/env python3
"""
Example: Simple melody using compound command with scheduled starts.

This example demonstrates creating a simple melody by using start_time
to schedule multiple notes at specific times, and fade_out for smooth endings.

WARNING: This will play audio!
"""

import time
from fa_launcher_audio import AudioManager


def data_provider(name: str) -> bytes:
    """Not used in this example."""
    raise FileNotFoundError(f"No files: {name}")


# Note frequencies (Hz)
NOTES = {
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "B4": 493.88,
    "C5": 523.25,
}


def main():
    print("Playing a simple melody using compound command...")
    print("(Press Ctrl+C to stop)")

    # Simple melody: C D E F G A B C (ascending scale)
    melody = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    note_duration = 0.4
    gap = 0.1
    fade_time = 0.05
    volume = 0.3

    # Build patch commands with start_time for each note
    commands = []
    current_time = 0.0

    for i, note in enumerate(melody):
        commands.append({
            "command": "patch",
            "id": f"note_{i}",
            "start_time": current_time,
            "source": {
                "kind": "waveform",
                "waveform": "sine",
                "frequency": NOTES[note],
                "non_looping_duration": note_duration,
                "fade_out": fade_time,
            },
            "volume": volume,
            "looping": False,
            "playback_rate": 1.0,
        })
        current_time += note_duration + gap

    total_duration = current_time + 0.5  # Add a little buffer at the end

    with AudioManager(data_provider=data_provider) as mgr:
        try:
            # Submit the entire melody as a compound command
            print(f"Playing {len(melody)} notes...")
            mgr.submit_command({
                "command": "compound",
                "commands": commands,
            })

            # Wait for the melody to complete
            time.sleep(total_duration)

        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
