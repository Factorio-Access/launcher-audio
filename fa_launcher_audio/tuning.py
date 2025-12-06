"""
Interactive tuning utility for audio files.

Uses ffmpeg for audio processing and the library's audio engine for playback.
Provides a menu-driven interface for trimming silence, auditioning,
pitch adjustment via bisection, and saving results.
"""

import atexit
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fa_launcher_audio import AudioManager
from fa_launcher_audio.pitch import note_to_frequency


# C4 reference frequency
C4_FREQ = note_to_frequency("C", 4)


def _getch_setup():
    """
    Set up platform-specific single-character input.

    Returns a function that reads a single character without requiring Enter.
    Falls back to input() if raw input is not available.
    """
    try:
        # Windows
        import msvcrt

        def getch():
            """Read a single character (Windows)."""
            return msvcrt.getch().decode("utf-8", errors="replace")

        def kbhit():
            """Check if a key is available (Windows)."""
            return msvcrt.kbhit()

        return getch, kbhit
    except ImportError:
        pass

    try:
        # Unix/Linux/Mac
        import termios
        import tty

        def getch():
            """Read a single character (Unix)."""
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch

        def kbhit():
            """Check if a key is available (Unix) - not implemented, always False."""
            return False

        return getch, kbhit
    except ImportError:
        pass

    # Fallback: require Enter after each character
    def getch_fallback():
        """Read input with Enter required (fallback)."""
        try:
            line = input()
            return line[0] if line else ""
        except EOFError:
            return "q"

    def kbhit_fallback():
        return False

    print("Note: Raw keyboard input not available. Press Enter after each command.")
    return getch_fallback, kbhit_fallback


# Set up keyboard input
_getch, _kbhit = _getch_setup()


class TuningSession:
    """Interactive tuning session for a single audio file."""

    def __init__(self, input_path: Path):
        self.input_path = input_path
        self.temp_dir = tempfile.mkdtemp(prefix="fa_tuning_")
        self.current_file = input_path
        self.pitch_ratio = 1.0  # Accumulated pitch adjustment
        self._manager = None

        # Register cleanup
        atexit.register(self._cleanup)

    def _cleanup(self):
        """Clean up temporary files."""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _make_temp_path(self, suffix: str = "") -> Path:
        """Create a unique temp file path."""
        timestamp = int(time.time() * 1000)
        ext = self.input_path.suffix
        name = f"tuning_{timestamp}{suffix}{ext}"
        return Path(self.temp_dir) / name

    def _run_ffmpeg(self, args: list[str], output_path: Path) -> bool:
        """Run ffmpeg with given arguments. Returns True on success."""
        cmd = ["ffmpeg", "-y", "-i", str(self.current_file)] + args + [str(output_path)]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr.decode()}")
            return False
        return True

    def _data_provider(self, name: str) -> bytes:
        """Provide audio data for the audio manager."""
        return self.current_file.read_bytes()

    def trim_silence(self) -> None:
        """Trim silence from the beginning and end of the audio."""
        print("\nTrimming silence...")
        output = self._make_temp_path("_trimmed")

        # silenceremove filter: remove silence from start, then reverse,
        # remove from "start" (which is actually end), reverse back
        filter_chain = (
            "silenceremove=start_periods=1:start_threshold=-50dB:start_duration=0.01,"
            "areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_duration=0.01,"
            "areverse"
        )

        if self._run_ffmpeg(["-af", filter_chain], output):
            self.current_file = output
            print("Silence trimmed successfully.")
        else:
            print("Failed to trim silence.")

    def audition(self) -> None:
        """Play the audio file once each time Enter is pressed. Q to quit."""
        print("\nAudition mode: Press Enter to play, Q to quit.")

        with AudioManager(self._data_provider, disable_cache=True) as mgr:
            while True:
                ch = _getch()
                if ch.lower() == "q":
                    # Stop any playing sound
                    mgr.submit_command({"command": "stop", "id": "audition"})
                    break
                elif ch in ("\r", "\n", ""):
                    # Stop previous, start new
                    mgr.submit_command({"command": "stop", "id": "audition"})
                    mgr.submit_command({
                        "command": "patch",
                        "id": "audition",
                        "source": {"kind": "encoded_bytes", "name": "current"},
                        "volume": 1.0,
                        "looping": False,
                        "playback_rate": 1.0,
                    })
                    print("Playing...")

        print("Audition mode ended.")

    def audition_looping(self) -> None:
        """Toggle looping playback on/off with Enter. Q to quit."""
        print("\nLooping audition mode: Press Enter to toggle playback, Q to quit.")

        playing = False
        with AudioManager(self._data_provider, disable_cache=True) as mgr:
            while True:
                ch = _getch()
                if ch.lower() == "q":
                    mgr.submit_command({"command": "stop", "id": "loop"})
                    break
                elif ch in ("\r", "\n", ""):
                    if playing:
                        mgr.submit_command({"command": "stop", "id": "loop"})
                        playing = False
                        print("Stopped.")
                    else:
                        mgr.submit_command({
                            "command": "patch",
                            "id": "loop",
                            "source": {"kind": "encoded_bytes", "name": "current"},
                            "volume": 1.0,
                            "looping": True,
                            "playback_rate": 1.0,
                        })
                        playing = True
                        print("Playing (looping)...")

        print("Looping audition mode ended.")

    def pitch_bisection(self) -> None:
        """
        Binary search for the correct pitch.

        Plays a C4 reference tone and loops the audio.
        User presses H if sample is too high, L if too low.
        Press Enter when satisfied to apply the adjustment with ffmpeg.
        Press Q to cancel.
        """
        print("\nPitch bisection mode:")
        print(f"  Reference: C4 ({C4_FREQ:.2f} Hz)")
        print("  H = sample sounds too HIGH (will lower it)")
        print("  L = sample sounds too LOW (will raise it)")
        print("  R = reset to original pitch")
        print("  Enter = apply current adjustment with ffmpeg")
        print("  Q = cancel")
        print()

        # Binary search bounds (in semitones from current)
        # Start with a wide range: +/- 2 octaves = +/- 24 semitones
        low_semitones = -24.0
        high_semitones = 24.0
        current_semitones = 0.0

        def semitones_to_ratio(semitones: float) -> float:
            """Convert semitones adjustment to pitch ratio."""
            return 2 ** (semitones / 12)

        with AudioManager(self._data_provider, disable_cache=True) as mgr:
            # Start reference tone
            mgr.submit_command({
                "command": "patch",
                "id": "reference",
                "source": {
                    "kind": "waveform",
                    "waveform": "sine",
                    "frequency": C4_FREQ,
                },
                "volume": 0.3,
                "looping": True,
                "playback_rate": 1.0,
            })

            # Start looping sample
            mgr.submit_command({
                "command": "patch",
                "id": "sample",
                "source": {"kind": "encoded_bytes", "name": "current"},
                "volume": 1.0,
                "looping": True,
                "playback_rate": semitones_to_ratio(current_semitones),
            })

            print(f"Current adjustment: {current_semitones:+.2f} semitones (ratio: {semitones_to_ratio(current_semitones):.4f})")

            while True:
                ch = _getch()

                if ch.lower() == "q":
                    print("Cancelled.")
                    mgr.submit_command({"command": "stop", "id": "reference"})
                    mgr.submit_command({"command": "stop", "id": "sample"})
                    return

                elif ch.lower() == "h":
                    # Too high - need to lower, so target is below current
                    high_semitones = current_semitones
                    current_semitones = (low_semitones + high_semitones) / 2

                elif ch.lower() == "l":
                    # Too low - need to raise, so target is above current
                    low_semitones = current_semitones
                    current_semitones = (low_semitones + high_semitones) / 2

                elif ch.lower() == "r":
                    # Reset
                    low_semitones = -24.0
                    high_semitones = 24.0
                    current_semitones = 0.0

                elif ch in ("\r", "\n", ""):
                    # Apply with ffmpeg
                    mgr.submit_command({"command": "stop", "id": "reference"})
                    mgr.submit_command({"command": "stop", "id": "sample"})
                    break

                else:
                    continue

                # Update playback rate
                ratio = semitones_to_ratio(current_semitones)
                mgr.submit_command({
                    "command": "patch",
                    "id": "sample",
                    "source": {"kind": "encoded_bytes", "name": "current"},
                    "volume": 1.0,
                    "looping": True,
                    "playback_rate": ratio,
                })
                print(f"Current adjustment: {current_semitones:+.2f} semitones (ratio: {ratio:.4f})")

        # Apply the adjustment with ffmpeg
        ratio = semitones_to_ratio(current_semitones)
        if abs(ratio - 1.0) < 0.0001:
            print("No significant pitch adjustment needed.")
            return

        print(f"\nApplying pitch shift: {current_semitones:+.2f} semitones (ratio: {ratio:.4f})...")
        output = self._make_temp_path("_pitched")

        # Try rubberband first, fall back to asetrate+atempo
        filter_arg = f"rubberband=pitch={ratio}"
        if self._run_ffmpeg(["-af", filter_arg], output):
            self.current_file = output
            self.pitch_ratio *= ratio
            print("Pitch adjusted successfully (using rubberband).")
        else:
            # Fallback
            filter_arg = f"asetrate=44100*{ratio},aresample=44100,atempo={1/ratio}"
            if self._run_ffmpeg(["-af", filter_arg], output):
                self.current_file = output
                self.pitch_ratio *= ratio
                print("Pitch adjusted successfully (using asetrate/atempo fallback).")
            else:
                print("Failed to apply pitch adjustment.")

    def save(self) -> None:
        """Save the current audio to a user-specified path."""
        print("\nSave output")

        # Suggest output path
        suggested = self.input_path.with_stem(f"{self.input_path.stem}_tuned")
        print(f"Suggested output: {suggested}")

        try:
            user_input = input("Enter output path (or press Enter for suggested): ").strip()
        except EOFError:
            user_input = ""

        if not user_input:
            output_path = suggested
        else:
            output_path = Path(user_input)

        # Copy current file to output
        try:
            shutil.copy2(self.current_file, output_path)
            print(f"Saved to: {output_path}")
        except Exception as e:
            print(f"Failed to save: {e}")

    def show_status(self) -> None:
        """Show current session status."""
        print(f"\n--- Status ---")
        print(f"Original file: {self.input_path}")
        print(f"Current file: {self.current_file}")
        print(f"Total pitch adjustment: {self.pitch_ratio:.4f}")
        if self.current_file != self.input_path:
            print("(Working with modified version)")

    def run(self) -> None:
        """Run the interactive tuning session."""
        print(f"\nTuning utility - {self.input_path.name}")
        print("=" * 50)

        while True:
            print("\n--- Menu ---")
            print("1. Trim silence")
            print("2. Audition (play on Enter)")
            print("3. Audition looping (toggle on Enter)")
            print("4. Pitch bisection")
            print("5. Save output")
            print("6. Show status")
            print("Q. Quit")
            print()

            try:
                choice = input("Choice: ").strip().lower()
            except EOFError:
                choice = "q"

            if choice == "1":
                self.trim_silence()
            elif choice == "2":
                self.audition()
            elif choice == "3":
                self.audition_looping()
            elif choice == "4":
                self.pitch_bisection()
            elif choice == "5":
                self.save()
            elif choice == "6":
                self.show_status()
            elif choice == "q":
                print("\nExiting...")
                break
            else:
                print("Invalid choice. Please try again.")

        # Cleanup is handled by atexit


def main():
    """Entry point for the tuning utility."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="fa-tune",
        description="Interactive audio tuning utility",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Audio file to tune",
    )

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    session = TuningSession(args.file)
    try:
        session.run()
    finally:
        session._cleanup()


if __name__ == "__main__":
    main()
