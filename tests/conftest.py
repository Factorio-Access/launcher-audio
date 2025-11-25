"""Pytest fixtures for fa_launcher_audio tests."""

import pytest
from pathlib import Path


@pytest.fixture
def test_audio_path():
    """Path to the test audio file."""
    return Path(__file__).parent.parent / "clang.flac"


@pytest.fixture
def test_audio_bytes(test_audio_path):
    """Test audio file as bytes."""
    return test_audio_path.read_bytes()


@pytest.fixture
def mock_bytes_callback(test_audio_bytes):
    """Mock bytes callback that returns the test audio."""
    def callback(name: str) -> bytes:
        # Return test audio for any name ending in .flac
        if name.endswith(".flac"):
            return test_audio_bytes
        # For other files, create a simple silent WAV
        return create_silent_wav()
    return callback


def create_silent_wav(duration_ms: int = 100, sample_rate: int = 44100) -> bytes:
    """Create a simple silent WAV file."""
    import struct

    num_samples = int(sample_rate * duration_ms / 1000)
    num_channels = 2
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align

    # WAV header
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size
        1,   # AudioFormat (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )

    # Silent data (all zeros)
    data = bytes(data_size)

    return header + data
