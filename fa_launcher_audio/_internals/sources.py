"""Audio data sources for miniaudio."""

from typing import Callable
from fa_launcher_audio._audio_cffi import ffi, lib
from fa_launcher_audio._internals.engine import _check_result


class WaveformSource:
    """
    Generates waveform audio (sine, square, triangle, sawtooth).

    This wraps miniaudio's ma_waveform generator.
    """

    TYPES = {
        "sine": lib.ma_waveform_type_sine,
        "square": lib.ma_waveform_type_square,
        "triangle": lib.ma_waveform_type_triangle,
        "saw": lib.ma_waveform_type_sawtooth,
        "sawtooth": lib.ma_waveform_type_sawtooth,
    }

    SAMPLE_RATE = 44100
    CHANNELS = 2

    def __init__(
        self,
        waveform_type: str,
        frequency: float,
        amplitude: float = 1.0,
        duration_seconds: float | None = None,
    ):
        """
        Create a waveform generator.

        Args:
            waveform_type: One of "sine", "square", "triangle", "saw"
            frequency: Frequency in Hz
            amplitude: Amplitude (0.0 to 1.0)
            duration_seconds: Duration in seconds (None for infinite)
        """
        self._initialized = False  # Set early to prevent __del__ errors

        if waveform_type not in self.TYPES:
            raise ValueError(
                f"Unknown waveform type: {waveform_type}. "
                f"Valid types: {list(self.TYPES.keys())}"
            )

        self._waveform = ffi.new("ma_waveform*")
        self._waveform_type = waveform_type
        self._frequency = frequency
        self._amplitude = amplitude
        self._duration_frames = (
            int(duration_seconds * self.SAMPLE_RATE) if duration_seconds else None
        )
        self._frames_read = 0

        # Configure waveform
        config = lib.ma_waveform_config_init(
            lib.ma_format_f32,
            self.CHANNELS,
            self.SAMPLE_RATE,
            self.TYPES[waveform_type],
            amplitude,
            frequency,
        )

        result = lib.ma_waveform_init(ffi.addressof(config), self._waveform)
        _check_result(result, f"Failed to initialize waveform ({waveform_type})")
        self._initialized = True

    def set_frequency(self, frequency: float) -> None:
        """Change the waveform frequency."""
        if self._initialized:
            self._frequency = frequency
            lib.ma_waveform_set_frequency(self._waveform, frequency)

    def set_amplitude(self, amplitude: float) -> None:
        """Change the waveform amplitude."""
        if self._initialized:
            self._amplitude = amplitude
            lib.ma_waveform_set_amplitude(self._waveform, amplitude)

    def reset(self) -> None:
        """Reset waveform to beginning."""
        if self._initialized:
            lib.ma_waveform_seek_to_pcm_frame(self._waveform, 0)
            self._frames_read = 0

    @property
    def is_finished(self) -> bool:
        """Check if the waveform has finished (only if duration was set)."""
        if self._duration_frames is None:
            return False
        return self._frames_read >= self._duration_frames

    def get_data_source_ptr(self):
        """Get pointer to underlying data source for ma_sound_init_from_data_source."""
        return self._waveform

    def cleanup(self) -> None:
        """Release resources."""
        if self._initialized:
            lib.ma_waveform_uninit(self._waveform)
            self._initialized = False

    def __del__(self):
        self.cleanup()


class DecoderSource:
    """
    Decodes audio from bytes (wav, flac, mp3, ogg).

    This wraps miniaudio's ma_decoder. Decodes to mono.
    """

    SAMPLE_RATE = 44100
    CHANNELS = 1  # Downmix to mono

    def __init__(self, audio_bytes: bytes):
        """
        Create a decoder from audio bytes.

        Args:
            audio_bytes: Raw audio file bytes (wav, flac, mp3, or ogg)
        """
        self._bytes = audio_bytes  # Keep reference to prevent GC
        self._decoder = ffi.new("ma_decoder*")
        self._initialized = False

        # Configure decoder for float32 stereo output at our sample rate
        config = lib.ma_decoder_config_init(
            lib.ma_format_f32, self.CHANNELS, self.SAMPLE_RATE
        )

        result = lib.ma_decoder_init_memory(
            ffi.from_buffer(self._bytes),
            len(self._bytes),
            ffi.addressof(config),
            self._decoder,
        )
        _check_result(result, "Failed to initialize decoder")
        self._initialized = True

    def get_length_frames(self) -> int:
        """Get total length in PCM frames."""
        if not self._initialized:
            return 0
        length = ffi.new("ma_uint64*")
        result = lib.ma_decoder_get_length_in_pcm_frames(self._decoder, length)
        if result != 0:
            return 0
        return int(length[0])

    def reset(self) -> None:
        """Reset decoder to beginning."""
        if self._initialized:
            lib.ma_decoder_seek_to_pcm_frame(self._decoder, 0)

    def get_data_source_ptr(self):
        """Get pointer to underlying data source for ma_sound_init_from_data_source."""
        return self._decoder

    def cleanup(self) -> None:
        """Release resources."""
        if self._initialized:
            lib.ma_decoder_uninit(self._decoder)
            self._initialized = False

    def __del__(self):
        self.cleanup()


class EncodedBytesSource:
    """
    Source that loads audio via a callback, then decodes it.

    This is the main interface for the "encoded_bytes" source type.
    """

    def __init__(
        self,
        name: str,
        bytes_callback: Callable[[str], bytes],
    ):
        """
        Create an encoded bytes source.

        Args:
            name: Name/path to pass to the callback
            bytes_callback: Callback that returns audio bytes for a given name
        """
        self._name = name
        self._decoder: DecoderSource | None = None

        # Load and decode the audio
        audio_bytes = bytes_callback(name)
        self._decoder = DecoderSource(audio_bytes)

    def get_length_frames(self) -> int:
        """Get total length in PCM frames."""
        if self._decoder:
            return self._decoder.get_length_frames()
        return 0

    def reset(self) -> None:
        """Reset to beginning."""
        if self._decoder:
            self._decoder.reset()

    def get_data_source_ptr(self):
        """Get pointer to underlying data source."""
        if self._decoder:
            return self._decoder.get_data_source_ptr()
        return ffi.NULL

    def cleanup(self) -> None:
        """Release resources."""
        if self._decoder:
            self._decoder.cleanup()
            self._decoder = None

    def __del__(self):
        self.cleanup()
