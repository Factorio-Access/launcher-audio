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


# C4 reference frequency (middle C)
# C4 is MIDI note 60, A4 (440 Hz) is MIDI note 69
# C4 = 440 * 2^((60-69)/12) = 261.626 Hz
C4_FREQ = 261.6255653005986


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
            # Check for Ctrl+C (returns \x03)
            ch = msvcrt.getch()
            if ch == b'\x03':
                raise KeyboardInterrupt
            return ch.decode("utf-8", errors="replace")

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
                # Check for Ctrl+C
                if ch == '\x03':
                    raise KeyboardInterrupt
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
        print("\nTrim silence settings:")
        print(f"  Current defaults: threshold=-50dB, min_duration=0.01s")
        print()

        # Get threshold
        try:
            thresh_input = input("Silence threshold in dB (Enter for -50): ").strip()
        except EOFError:
            thresh_input = ""
        threshold = int(thresh_input) if thresh_input else -50

        # Get minimum duration
        try:
            dur_input = input("Minimum silence duration in seconds (Enter for 0.01): ").strip()
        except EOFError:
            dur_input = ""
        min_duration = float(dur_input) if dur_input else 0.01

        print(f"\nTrimming with threshold={threshold}dB, min_duration={min_duration}s...")
        output = self._make_temp_path("_trimmed")

        # silenceremove filter: remove silence from start, then reverse,
        # remove from "start" (which is actually end), reverse back
        filter_chain = (
            f"silenceremove=start_periods=1:start_threshold={threshold}dB:start_duration={min_duration},"
            "areverse,"
            f"silenceremove=start_periods=1:start_threshold={threshold}dB:start_duration={min_duration},"
            "areverse"
        )

        if self._run_ffmpeg(["-af", filter_chain], output):
            self.current_file = output
            print("Silence trimmed successfully.")
        else:
            print("Failed to trim silence.")

    def denoise(self) -> None:
        """Apply noise reduction using ffmpeg's afftdn filter."""
        print("\nDenoise settings (using FFT-based denoiser):")
        print("  nr = noise reduction amount in dB (higher = more reduction)")
        print("  nf = noise floor in dB (audio below this is considered noise)")
        print()

        # Get noise reduction amount
        try:
            nr_input = input("Noise reduction in dB (Enter for 12): ").strip()
        except EOFError:
            nr_input = ""
        noise_reduction = float(nr_input) if nr_input else 12.0

        # Get noise floor
        try:
            nf_input = input("Noise floor in dB (Enter for -50): ").strip()
        except EOFError:
            nf_input = ""
        noise_floor = float(nf_input) if nf_input else -50.0

        print(f"\nApplying denoise: nr={noise_reduction}dB, nf={noise_floor}dB...")
        output = self._make_temp_path("_denoised")

        # afftdn: FFT-based denoiser
        # nr = noise reduction, nf = noise floor, tn = track noise (adapts over time)
        filter_arg = f"afftdn=nr={noise_reduction}:nf={noise_floor}:tn=1"

        if self._run_ffmpeg(["-af", filter_arg], output):
            self.current_file = output
            print("Denoise applied successfully.")
        else:
            print("Failed to apply denoise.")

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
        print(f"Copying from: {self.current_file}")
        try:
            shutil.copy2(self.current_file, output_path)
            print(f"Saved to: {output_path}")
        except Exception as e:
            print(f"Failed to save: {e}")

    def trim_bisection(self) -> None:
        """
        Binary search for the right trim point at the end.

        Plays audio from a candidate cut point to the end.
        User indicates if they hear wanted audio (cut is too early)
        or unwanted tail (cut is too late).
        """
        print("\nTrim bisection mode:")
        print("  Plays from candidate cut point to end of file.")
        print("  E = cut is too EARLY (I hear audio I want to keep)")
        print("  L = cut is too LATE (I still hear unwanted tail)")
        print("  R = reset to full range")
        print("  Enter = apply trim at current point")
        print("  Q = cancel")
        print()

        # Get file duration
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(self.current_file)],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 1.0

        # Binary search bounds (in seconds from start)
        # Start assuming we want to keep at least the first 10% and cut at most 90%
        low = duration * 0.1  # Earliest possible cut
        high = duration  # Latest possible cut (no trim)
        current = duration * 0.8  # Start at 80% of the way through

        # Create a stable preview file path
        preview_file = self._make_temp_path("_preview")
        original_file = self.current_file

        # Data provider that always reads from preview_file
        def preview_provider(name: str) -> bytes:
            data = preview_file.read_bytes()
            print(f"  [Provider] Reading {len(data)} bytes from {preview_file.name}")
            return data

        print(f"File duration: {duration:.3f}s")
        print(f"Current cut point: {current:.3f}s (keeping first {current:.3f}s)")
        print("Playing from start to cut point (looping what you'll KEEP)...")

        # Create initial preview - from start TO cut point (what we're keeping)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(original_file),
             "-t", str(current), "-f", "wav", str(preview_file)],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr.decode()}")
            return
        if not preview_file.exists():
            print(f"Preview file not created: {preview_file}")
            return

        with AudioManager(preview_provider, disable_cache=True) as mgr:
            mgr.submit_command({
                "command": "patch",
                "id": "trim_preview",
                "source": {"kind": "encoded_bytes", "name": "preview"},
                "volume": 1.0,
                "looping": True,
                "playback_rate": 1.0,
            })
            time.sleep(0.1)  # Let audio start

            while True:
                ch = _getch()

                if ch.lower() == "q":
                    print("Cancelled.")
                    mgr.submit_command({"command": "stop", "id": "trim_preview"})
                    return

                elif ch.lower() == "e":
                    # Too early - hearing wanted audio, move cut point later
                    low = current
                    current = (low + high) / 2

                elif ch.lower() == "l":
                    # Too late - still hearing tail, move cut point earlier
                    high = current
                    current = (low + high) / 2

                elif ch.lower() == "r":
                    # Reset
                    low = duration * 0.1
                    high = duration
                    current = duration * 0.8

                elif ch in ("\r", "\n", ""):
                    # Apply trim
                    mgr.submit_command({"command": "stop", "id": "trim_preview"})
                    break

                else:
                    continue

                # Update preview
                print(f"Cut point: {current:.3f}s (keeping first {current:.3f}s, trimming {duration - current:.3f}s)")

                # Stop current playback and wait for it to fully stop
                mgr.submit_command({"command": "stop", "id": "trim_preview"})
                time.sleep(0.1)  # Wait for sound to fully stop and be cleaned up

                # Create new preview - from start TO cut point (what we're keeping)
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(original_file),
                     "-t", str(current), "-f", "wav", str(preview_file)],
                    capture_output=True
                )
                if result.returncode != 0:
                    print(f"ffmpeg error: {result.stderr.decode()}")
                    continue

                # Verify file was updated
                size = preview_file.stat().st_size
                print(f"  Preview: {size} bytes, keeping {current:.3f}s")

                # Start playing new preview
                mgr.submit_command({
                    "command": "patch",
                    "id": "trim_preview",
                    "source": {"kind": "encoded_bytes", "name": "preview"},
                    "volume": 1.0,
                    "looping": True,
                    "playback_rate": 1.0,
                })
                time.sleep(0.1)  # Let new sound start

        # Apply the trim
        if current >= duration - 0.001:
            print("No trim needed.")
            return

        print(f"\nApplying trim: keeping first {current:.3f}s (removing {duration - current:.3f}s)...")
        print(f"  Source: {original_file}")
        output = self._make_temp_path("_end_trimmed")
        print(f"  Output: {output}")

        # Use original file as input for final trim
        cmd = ["ffmpeg", "-y", "-i", str(original_file), "-t", str(current), str(output)]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            self.current_file = output
            print(f"End trimmed successfully. Current file is now: {self.current_file}")
        else:
            print(f"Failed to trim: {result.stderr.decode()}")

    def analyze(self) -> None:
        """Analyze audio levels and silence regions."""
        print("\nAnalyzing audio...")

        # Get basic file info
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(self.current_file)],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0

        # Silence detection at various thresholds
        print(f"\nFile duration: {duration:.3f}s")
        print("\nSilence detection at different thresholds:")

        for threshold in [-30, -40, -50, -60]:
            result = subprocess.run(
                ["ffmpeg", "-i", str(self.current_file),
                 "-af", f"silencedetect=noise={threshold}dB:d=0.01",
                 "-f", "null", "-"],
                capture_output=True, text=True
            )
            # Parse silence regions from stderr
            lines = [l for l in result.stderr.split('\n') if 'silence_start' in l or 'silence_end' in l]
            if lines:
                print(f"\n  {threshold}dB threshold:")
                for line in lines[-4:]:  # Show last few
                    if 'silence_start' in line:
                        start = line.split('silence_start:')[1].strip()
                        print(f"    silence starts: {float(start):.3f}s")
                    elif 'silence_end' in line:
                        parts = line.split('|')
                        end = parts[0].split('silence_end:')[1].strip()
                        dur = parts[1].split('silence_duration:')[1].strip() if len(parts) > 1 else "?"
                        print(f"    silence ends: {float(end):.3f}s (duration: {dur}s)")
            else:
                print(f"  {threshold}dB: no silence detected")

        # Volume stats
        result = subprocess.run(
            ["ffmpeg", "-i", str(self.current_file),
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True
        )
        print("\nVolume statistics:")
        for line in result.stderr.split('\n'):
            if 'mean_volume' in line or 'max_volume' in line:
                print(f"  {line.split(']')[1].strip()}")

        # Noise floor from astats
        result = subprocess.run(
            ["ffmpeg", "-i", str(self.current_file),
             "-af", "astats", "-f", "null", "-"],
            capture_output=True, text=True
        )
        for line in result.stderr.split('\n'):
            if 'Noise floor dB' in line:
                print(f"  {line.split(']')[1].strip()}")
                break

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
            print("1. Trim silence (threshold-based)")
            print("2. Trim bisection (interactive)")
            print("3. Denoise")
            print("4. Audition (play on Enter)")
            print("5. Audition looping (toggle on Enter)")
            print("6. Pitch bisection")
            print("7. Analyze audio levels")
            print("8. Save output")
            print("9. Show status")
            print("Q. Quit")
            print()

            try:
                choice = input("Choice: ").strip().lower()
            except EOFError:
                choice = "q"

            if choice == "1":
                self.trim_silence()
            elif choice == "2":
                self.trim_bisection()
            elif choice == "3":
                self.denoise()
            elif choice == "4":
                self.audition()
            elif choice == "5":
                self.audition_looping()
            elif choice == "6":
                self.pitch_bisection()
            elif choice == "7":
                self.analyze()
            elif choice == "8":
                self.save()
            elif choice == "9":
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
