#!/usr/bin/env python3
"""
Example: Static playback of a file.

This example demonstrates loading and playing an audio file.

WARNING: This will play audio!
"""

import time
from pathlib import Path
import sys

from fa_launcher_audio import AudioManager


def data_provider(name: str) -> bytes:
    """Load audio file from disk."""
    # Look for files relative to the project root
    project_root = Path(__file__).parent.parent
    file_path = project_root / name
    if file_path.exists():
        return file_path.read_bytes()
    raise FileNotFoundError(f"Audio file not found: {name}")


def main():
    print("Playing", sys.argv[1])
    print("(Press Ctrl+C to stop)")

    with AudioManager(data_provider=data_provider) as mgr:
        # Play the test audio file
        mgr.submit_command({
            "command": "patch",
            "id": "music",
            "source": {
                "kind": "encoded_bytes",
                "name": sys.argv[1],
            },
            "volume": 0.5,  # 50% volume
            "pan": 0.0,
            "looping": False,
            "playback_rate": 1.0,
        })

        # Wait for playback
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
