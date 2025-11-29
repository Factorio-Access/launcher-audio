"""
Pitch detection and shifting utilities.

Uses YIN algorithm for pitch detection and ffmpeg for pitch shifting.
Based on: De Cheveigné & Kawahara (2002), "YIN, a fundamental frequency
estimator for speech and music"
"""

import subprocess
import wave
from pathlib import Path

import numpy as np


# Note frequencies (A4 = 440 Hz standard tuning)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
A4_FREQ = 440.0
A4_MIDI = 69


def frequency_to_note(freq: float) -> tuple[str, int, float]:
    """
    Convert frequency to note name, octave, and cents deviation.

    Args:
        freq: Frequency in Hz

    Returns:
        Tuple of (note_name, octave, cents_deviation)
    """
    if freq <= 0:
        return ("?", 0, 0.0)

    # Calculate MIDI note number (can be fractional)
    midi_note = 12 * np.log2(freq / A4_FREQ) + A4_MIDI

    # Round to nearest note
    midi_rounded = round(midi_note)

    # Calculate cents deviation (-50 to +50)
    cents = (midi_note - midi_rounded) * 100

    # Get note name and octave
    note_index = midi_rounded % 12
    octave = (midi_rounded // 12) - 1

    return (NOTE_NAMES[note_index], octave, cents)


def note_to_frequency(note: str, octave: int) -> float:
    """
    Convert note name and octave to frequency.

    Args:
        note: Note name (e.g., "C", "F#", "Bb")
        octave: Octave number (4 = middle octave, A4 = 440Hz)

    Returns:
        Frequency in Hz
    """
    # Normalize note name
    note = note.upper().replace("B", "#").rstrip("#")
    if note.endswith("B"):
        # Handle flats by converting to sharps
        idx = NOTE_NAMES.index(note[0])
        note = NOTE_NAMES[(idx - 1) % 12]

    # Handle sharp
    if "#" in note or note not in NOTE_NAMES:
        # Find base note
        base = note.replace("#", "")
        if base in NOTE_NAMES:
            idx = NOTE_NAMES.index(base)
            sharps = note.count("#")
            note_index = (idx + sharps) % 12
        else:
            raise ValueError(f"Unknown note: {note}")
    else:
        note_index = NOTE_NAMES.index(note)

    # Calculate MIDI note number
    midi_note = note_index + (octave + 1) * 12

    # Convert to frequency
    return A4_FREQ * (2 ** ((midi_note - A4_MIDI) / 12))


def _difference_function(signal: np.ndarray, max_tau: int) -> np.ndarray:
    """
    Compute the YIN difference function.

    d(τ) = Σ (x[j] - x[j+τ])²

    Uses autocorrelation via FFT for efficiency.
    """
    n = len(signal)

    # Pad for FFT
    fft_size = 1
    while fft_size < 2 * n:
        fft_size *= 2

    # Compute autocorrelation using FFT
    signal_padded = np.zeros(fft_size)
    signal_padded[:n] = signal

    fft_signal = np.fft.rfft(signal_padded)
    acf = np.fft.irfft(fft_signal * np.conj(fft_signal))

    # Compute cumulative sum of squared signal for difference function
    # d(τ) = r(0) + r_shifted(0) - 2*r(τ)
    # where r is autocorrelation

    signal_sq = signal ** 2
    cum_sum = np.cumsum(signal_sq)
    cum_sum_shifted = np.cumsum(signal_sq[::-1])[::-1]

    # Build difference function
    diff = np.zeros(max_tau)
    diff[0] = 0

    for tau in range(1, max_tau):
        # Sum of (x[j] - x[j+tau])^2 for j in [0, n-tau)
        # = sum(x[j]^2) + sum(x[j+tau]^2) - 2*sum(x[j]*x[j+tau])
        diff[tau] = cum_sum[n - tau - 1] + (cum_sum_shifted[0] - cum_sum_shifted[tau]) - 2 * acf[tau]

    return diff


def _cumulative_mean_normalized_difference(diff: np.ndarray) -> np.ndarray:
    """
    Compute cumulative mean normalized difference function (CMNDF).

    d'(τ) = 1 if τ = 0
    d'(τ) = d(τ) / ((1/τ) * Σ d(k) for k=1 to τ) otherwise
    """
    cmndf = np.zeros_like(diff)
    cmndf[0] = 1.0

    running_sum = 0.0
    for tau in range(1, len(diff)):
        running_sum += diff[tau]
        if running_sum == 0:
            cmndf[tau] = 1.0
        else:
            cmndf[tau] = diff[tau] * tau / running_sum

    return cmndf


def _parabolic_interpolation(array: np.ndarray, index: int) -> float:
    """
    Refine peak/trough location using parabolic interpolation.

    Returns the interpolated x position of the minimum.
    """
    if index <= 0 or index >= len(array) - 1:
        return float(index)

    y0 = array[index - 1]
    y1 = array[index]
    y2 = array[index + 1]

    # Parabolic interpolation formula
    denom = 2 * (2 * y1 - y0 - y2)
    if abs(denom) < 1e-10:
        return float(index)

    shift = (y0 - y2) / denom
    return index + shift


def detect_pitch_yin(
    signal: np.ndarray,
    sample_rate: int,
    threshold: float = 0.1,
    f_min: float = 50.0,
    f_max: float = 2000.0,
) -> tuple[float | None, float]:
    """
    Detect fundamental frequency using the YIN algorithm.

    Args:
        signal: Audio signal as numpy array (mono)
        sample_rate: Sample rate in Hz
        threshold: Confidence threshold for CMNDF (lower = stricter)
        f_min: Minimum frequency to detect
        f_max: Maximum frequency to detect

    Returns:
        Tuple of (frequency in Hz or None if not found, confidence 0-1)
    """
    # Convert frequency bounds to lag bounds
    tau_min = max(2, int(sample_rate / f_max))
    tau_max = min(len(signal) // 2, int(sample_rate / f_min))

    if tau_max <= tau_min:
        return None, 0.0

    # Compute difference function and CMNDF
    diff = _difference_function(signal, tau_max)
    cmndf = _cumulative_mean_normalized_difference(diff)

    # Find first minimum below threshold
    tau_estimate = None
    min_val = float('inf')

    for tau in range(tau_min, tau_max - 1):
        if cmndf[tau] < threshold:
            # Check if it's a local minimum
            if cmndf[tau] < cmndf[tau - 1] and cmndf[tau] <= cmndf[tau + 1]:
                tau_estimate = tau
                min_val = cmndf[tau]
                break

    # If no value below threshold, find global minimum
    if tau_estimate is None:
        tau_estimate = tau_min + np.argmin(cmndf[tau_min:tau_max])
        min_val = cmndf[tau_estimate]

    # Parabolic interpolation for sub-sample accuracy
    tau_refined = _parabolic_interpolation(cmndf, tau_estimate)

    # Convert lag to frequency
    if tau_refined <= 0:
        return None, 0.0

    frequency = sample_rate / tau_refined
    confidence = max(0.0, min(1.0, 1.0 - min_val))

    return frequency, confidence


def detect_pitch_from_file(
    path: str | Path,
    threshold: float = 0.1,
    f_min: float = 50.0,
    f_max: float = 2000.0,
) -> tuple[float | None, float]:
    """
    Detect fundamental frequency from an audio file.

    Currently supports WAV files. Uses ffmpeg to convert other formats.

    Args:
        path: Path to audio file
        threshold: YIN threshold (lower = stricter)
        f_min: Minimum frequency to detect
        f_max: Maximum frequency to detect

    Returns:
        Tuple of (frequency in Hz or None, confidence 0-1)
    """
    path = Path(path)

    # For non-WAV files, use ffmpeg to convert to WAV in memory
    if path.suffix.lower() not in [".wav"]:
        result = subprocess.run(
            [
                "ffmpeg", "-i", str(path),
                "-f", "wav",
                "-acodec", "pcm_s16le",
                "-ac", "1",  # mono
                "-ar", "44100",  # resample to 44.1kHz
                "-"
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")

        # Parse WAV from stdout
        import io
        wav_data = io.BytesIO(result.stdout)
        with wave.open(wav_data, 'rb') as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_data = wf.readframes(n_frames)
            signal = np.frombuffer(raw_data, dtype=np.int16).astype(np.float64)
    else:
        with wave.open(str(path), 'rb') as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw_data = wf.readframes(n_frames)

            # Convert to numpy array
            if sample_width == 1:
                signal = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float64) - 128
            elif sample_width == 2:
                signal = np.frombuffer(raw_data, dtype=np.int16).astype(np.float64)
            elif sample_width == 4:
                signal = np.frombuffer(raw_data, dtype=np.int32).astype(np.float64)
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            # Convert to mono if stereo
            if n_channels > 1:
                signal = signal.reshape(-1, n_channels).mean(axis=1)

    # Normalize
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        signal = signal / max_val

    # Use middle portion of the file for detection (avoid silence at start/end)
    # Take a ~1 second chunk from the middle
    chunk_size = min(len(signal), sample_rate)
    start = (len(signal) - chunk_size) // 2
    chunk = signal[start:start + chunk_size]

    return detect_pitch_yin(chunk, sample_rate, threshold, f_min, f_max)


def shift_pitch_ffmpeg(
    input_path: str | Path,
    output_path: str | Path,
    ratio: float,
    use_rubberband: bool = True,
) -> None:
    """
    Shift pitch of an audio file using ffmpeg.

    Args:
        input_path: Source audio file
        output_path: Destination audio file
        ratio: Pitch multiplier (0.5 = octave down, 2.0 = octave up)
        use_rubberband: Use rubberband filter (better quality) if available
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if use_rubberband:
        # Try rubberband first (better quality, preserves duration)
        filter_arg = f"rubberband=pitch={ratio}"
    else:
        # Fallback: asetrate changes pitch but also duration,
        # then atempo compensates. Quality is lower.
        # asetrate=44100*ratio changes pitch, atempo=1/ratio restores duration
        filter_arg = f"asetrate=44100*{ratio},aresample=44100,atempo={1/ratio}"

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", filter_arg,
            str(output_path)
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode()
        # If rubberband failed, try fallback
        if use_rubberband and "rubberband" in stderr.lower():
            shift_pitch_ffmpeg(input_path, output_path, ratio, use_rubberband=False)
        else:
            raise RuntimeError(f"ffmpeg failed: {stderr}")


def compute_pitch_ratio(detected_hz: float, target_hz: float) -> float:
    """
    Compute the pitch ratio needed to shift from detected to target frequency.

    Args:
        detected_hz: Current frequency in Hz
        target_hz: Desired frequency in Hz

    Returns:
        Pitch multiplier (use with shift_pitch_ffmpeg or Sound.set_pitch)
    """
    return target_hz / detected_hz
