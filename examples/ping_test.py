"""
Test waveform ID reuse - plays repeated pings using the same ID.

This tests that IDs can be reused after a waveform finishes.
"""

import time
from fa_launcher_audio import AudioManager


def dummy_data_provider(name: str) -> bytes:
    """Not used for waveforms."""
    return b""


def main():
    with AudioManager(data_provider=dummy_data_provider) as mgr:
        print("Playing 10 pings with the same ID ('ping')...")
        print("Each ping is 0.2s with 0.05s fade_out, spaced 0.5s apart")
        print()

        for i in range(10):
            freq = 440 + (i * 50)  # Rising pitch
            print(f"Ping {i + 1}: {freq} Hz")

            mgr.submit_command({
                "command": "patch",
                "id": "ping",  # Same ID every time
                "source": {
                    "kind": "waveform",
                    "waveform": "sine",
                    "frequency": freq,
                    "non_looping_duration": 0.2,
                    "fade_out": 0.05,
                },
                "volume": 0.3,
            })

            time.sleep(0.5)

        print()
        print("Done! If you heard 10 distinct pings, ID reuse is working.")


if __name__ == "__main__":
    main()
