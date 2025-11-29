"""
Command-line interface for pitch detection and shifting.

Requires ffmpeg to be installed and available on PATH.
"""

import argparse
import json
import sys
from pathlib import Path

from fa_launcher_audio.pitch import (
    detect_pitch_from_file,
    frequency_to_note,
    note_to_frequency,
    compute_pitch_ratio,
    shift_pitch_ffmpeg,
)


def parse_target_pitch(target: str) -> float:
    """
    Parse target pitch from string.

    Accepts:
        - Frequency in Hz: "440", "261.63"
        - Note name with octave: "C4", "A4", "F#3"
    """
    # Try parsing as float first
    try:
        return float(target)
    except ValueError:
        pass

    # Parse as note name
    # Extract note and octave
    note = ""
    octave_str = ""

    for i, char in enumerate(target):
        if char.isdigit() or (char == '-' and i > 0):
            octave_str = target[i:]
            break
        note += char

    if not note or not octave_str:
        raise ValueError(f"Cannot parse target pitch: {target}")

    try:
        octave = int(octave_str)
    except ValueError:
        raise ValueError(f"Cannot parse octave from: {target}")

    return note_to_frequency(note, octave)


def cmd_analyze(args):
    """Analyze pitch of audio files."""
    results = {}

    for path_str in args.files:
        path = Path(path_str)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            continue

        try:
            freq, confidence = detect_pitch_from_file(
                path,
                threshold=args.threshold,
                f_min=args.f_min,
                f_max=args.f_max,
            )

            if freq is None:
                print(f"{path.name}: No pitch detected")
                results[str(path)] = None
            else:
                note, octave, cents = frequency_to_note(freq)
                cents_str = f"+{cents:.0f}" if cents >= 0 else f"{cents:.0f}"

                print(
                    f"{path.name}: {freq:.2f} Hz "
                    f"({note}{octave} {cents_str}c) "
                    f"[confidence: {confidence:.1%}]"
                )

                results[str(path)] = {
                    "frequency": freq,
                    "note": note,
                    "octave": octave,
                    "cents": cents,
                    "confidence": confidence,
                }

        except Exception as e:
            print(f"{path.name}: Error - {e}", file=sys.stderr)
            results[str(path)] = {"error": str(e)}

    if args.json:
        print(json.dumps(results, indent=2))


def cmd_shift(args):
    """Shift pitch of audio files to target."""
    target_hz = parse_target_pitch(args.target)
    target_note, target_octave, _ = frequency_to_note(target_hz)

    print(f"Target pitch: {target_hz:.2f} Hz ({target_note}{target_octave})")
    print()

    for path_str in args.files:
        path = Path(path_str)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            continue

        try:
            # Detect current pitch
            freq, confidence = detect_pitch_from_file(
                path,
                threshold=args.threshold,
                f_min=args.f_min,
                f_max=args.f_max,
            )

            if freq is None:
                print(f"{path.name}: No pitch detected, skipping")
                continue

            note, octave, cents = frequency_to_note(freq)
            ratio = compute_pitch_ratio(freq, target_hz)

            # Determine output path
            if args.output_dir:
                output_path = Path(args.output_dir) / path.name
            elif args.suffix:
                output_path = path.with_stem(f"{path.stem}{args.suffix}")
            else:
                output_path = path.with_stem(f"{path.stem}_shifted")

            output_path.parent.mkdir(parents=True, exist_ok=True)

            print(
                f"{path.name}: {freq:.2f} Hz ({note}{octave}) "
                f"-> ratio {ratio:.4f} -> {output_path.name}"
            )

            if not args.dry_run:
                shift_pitch_ffmpeg(path, output_path, ratio)

        except Exception as e:
            print(f"{path.name}: Error - {e}", file=sys.stderr)

    if args.dry_run:
        print("\n(dry run - no files modified)")


def cmd_ratio(args):
    """Calculate pitch ratio needed to shift between frequencies."""
    target_hz = parse_target_pitch(args.target)

    results = {}

    for path_str in args.files:
        path = Path(path_str)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            continue

        try:
            freq, confidence = detect_pitch_from_file(
                path,
                threshold=args.threshold,
                f_min=args.f_min,
                f_max=args.f_max,
            )

            if freq is None:
                print(f"{path.name}: No pitch detected")
                results[path.name] = None
            else:
                ratio = compute_pitch_ratio(freq, target_hz)
                note, octave, _ = frequency_to_note(freq)
                print(f"{path.name}: {freq:.2f} Hz ({note}{octave}) -> ratio: {ratio:.6f}")
                results[path.name] = ratio

        except Exception as e:
            print(f"{path.name}: Error - {e}", file=sys.stderr)

    if args.json:
        print("\nJSON output:")
        print(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="fa-pitch",
        description="Pitch detection and shifting for audio files",
    )

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.1,
        help="YIN detection threshold (default: 0.1, lower = stricter)",
    )
    common.add_argument(
        "--f-min",
        type=float,
        default=50.0,
        help="Minimum frequency to detect in Hz (default: 50)",
    )
    common.add_argument(
        "--f-max",
        type=float,
        default=2000.0,
        help="Maximum frequency to detect in Hz (default: 2000)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        parents=[common],
        help="Analyze and display pitch of audio files",
    )
    analyze_parser.add_argument("files", nargs="+", help="Audio files to analyze")
    analyze_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON",
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # Shift command
    shift_parser = subparsers.add_parser(
        "shift",
        parents=[common],
        help="Shift pitch of audio files to target",
    )
    shift_parser.add_argument("target", help="Target pitch (e.g., 'C4', '440', 'A4')")
    shift_parser.add_argument("files", nargs="+", help="Audio files to process")
    shift_parser.add_argument(
        "--output-dir", "-o",
        help="Output directory for shifted files",
    )
    shift_parser.add_argument(
        "--suffix", "-s",
        help="Suffix for output files (default: '_shifted')",
    )
    shift_parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without modifying files",
    )
    shift_parser.set_defaults(func=cmd_shift)

    # Ratio command
    ratio_parser = subparsers.add_parser(
        "ratio",
        parents=[common],
        help="Calculate pitch ratios without modifying files",
    )
    ratio_parser.add_argument("target", help="Target pitch (e.g., 'C4', '440')")
    ratio_parser.add_argument("files", nargs="+", help="Audio files to analyze")
    ratio_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON",
    )
    ratio_parser.set_defaults(func=cmd_ratio)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
