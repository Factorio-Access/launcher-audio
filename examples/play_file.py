#!/usr/bin/env python3
"""
Example: Static playback of a file with optional LPF.

Usage:
    python play_file.py <file> [lpf_cutoff] [volume] [filter_gain]

Arguments:
    file         Path to audio file (required)
    lpf_cutoff   Low-pass filter cutoff in Hz (optional, enables LPF)
    volume       Volume/gain 0.0-2.0 (optional, default 0.5)
    filter_gain  Filter blend 0.0-1.0 (optional, default 1.0 = fully filtered)

Examples:
    python play_file.py music.flac
    python play_file.py music.flac 500
    python play_file.py music.flac 500 0.8
    python play_file.py music.flac 500 0.8 0.5

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
    if len(sys.argv) < 2:
        print("Usage: python play_file.py <file> [lpf_cutoff] [volume] [filter_gain]")
        sys.exit(1)

    file_path = sys.argv[1]
    lpf_cutoff = float(sys.argv[2]) if len(sys.argv) > 2 else None
    volume = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    filter_gain = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    print(f"Playing: {file_path}")
    print(f"  Volume: {volume}")
    if lpf_cutoff:
        print(f"  LPF cutoff: {lpf_cutoff} Hz")
        print(f"  Filter gain: {filter_gain}")
    print("(Press Ctrl+C to stop)")

    with AudioManager(data_provider=data_provider) as mgr:
        # Build the command
        cmd = {
            "command": "patch",
            "id": "music",
            "source": {
                "kind": "encoded_bytes",
                "name": file_path,
            },
            "volume": volume,
            "pan": 0.0,
            "looping": False,
            "playback_rate": 1.0,
        }

        # Add LPF if cutoff specified
        if lpf_cutoff:
            cmd["lpf"] = {
                "cutoff": lpf_cutoff,
                "enabled": True,
            }
            cmd["filter_gain"] = filter_gain

        mgr.submit_command(cmd)

        # Wait for playback
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            pass

        print("Done!")


if __name__ == "__main__":
    main()
