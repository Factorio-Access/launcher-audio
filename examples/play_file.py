#!/usr/bin/env python3
"""
Example: Static playback of a file.

This example demonstrates loading and playing an audio file.

WARNING: This will play audio!
"""

import time
from pathlib import Path
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
    print("Playing clang.flac...")
    print("(Press Ctrl+C to stop)")

    with AudioManager(data_provider=data_provider) as mgr:
        # Play the test audio file
        mgr.submit_command({
            "command": "patch",
            "id": "music",
            "source": {
                "kind": "encoded_bytes",
                "name": "clang.flac",
            },
            "gains": {
                "overall": 0.5,  # 50% volume
                "left": 1.0,
                "right": 1.0,
            },
            "looping": False,
            "playback_rate": 1.0,
            "gains": {
                "overall":1,
                "left":0.5,
                "right": 1.0,
            },
        })

        # Wait for playback
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
