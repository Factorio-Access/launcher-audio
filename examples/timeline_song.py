#!/usr/bin/env python3
"""
Example: Simple melody using waveforms.

This example demonstrates creating a simple melody by sequencing
individual waveform sounds. Note: Timeline feature is planned for
a future version; this example uses manual timing.

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


def play_note(mgr, note_id: str, frequency: float, duration: float):
    """Play a single note with fade-in and fade-out."""
    mgr.submit_command({
        "command": "patch",
        "id": note_id,
        "source": {
            "kind": "waveform",
            "waveform": "sine",
            "frequency": frequency,
            "non_looping_duration": duration,
        },
        "gains": {
            "overall": [
                {"time": 0.0, "value": 0.0, "interpolation_from_prev": "linear"},
                {"time": 0.05, "value": 0.3, "interpolation_from_prev": "linear"},
                {"time": duration - 0.1, "value": 0.3, "interpolation_from_prev": "linear"},
                {"time": duration, "value": 0.0, "interpolation_from_prev": "linear"},
            ],
            "left": 1.0,
            "right": 1.0,
        },
        "looping": False,
        "playback_rate": 1.0,
    })


def main():
    print("Playing a simple melody...")
    print("(Press Ctrl+C to stop)")

    # Simple melody: C D E F G A B C (ascending scale)
    melody = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    note_duration = 0.4
    gap = 0.1

    with AudioManager(data_provider=data_provider) as mgr:
        try:
            for i, note in enumerate(melody):
                print(f"Playing {note}")
                play_note(mgr, f"note_{i}", NOTES[note], note_duration)
                time.sleep(note_duration + gap)

            # Wait a moment after the last note
            time.sleep(0.5)
        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
