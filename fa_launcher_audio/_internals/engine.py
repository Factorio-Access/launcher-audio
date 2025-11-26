"""MiniaudioEngine - Low-level wrapper around ma_engine."""

from fa_launcher_audio._audio_cffi import ffi, lib


class MiniaudioError(Exception):
    """Exception raised for miniaudio errors."""

    def __init__(self, result: int, message: str = ""):
        self.result = result
        super().__init__(f"Miniaudio error {result}: {message}")


def _check_result(result: int, message: str = "") -> None:
    """Raise MiniaudioError if result is not MA_SUCCESS (0)."""
    if result != 0:
        raise MiniaudioError(result, message)


class MiniaudioEngine:
    """
    Low-level wrapper around ma_engine.

    Provides Python-friendly interface to miniaudio's high-level engine API.
    """

    SAMPLE_RATE = 44100
    CHANNELS = 2

    def __init__(self, no_device: bool = False):
        """
        Initialize the audio engine.

        Args:
            no_device: If True, don't create an audio device (for testing/offline rendering).
        """
        self._engine = ffi.new("ma_engine*")
        self._initialized = False
        self._no_device = no_device

        # Get default config
        config = lib.ma_engine_config_init()

        # Note: For no_device mode, we'd need to modify the config
        # but since we're using opaque structs, we can't easily do that.
        # For now, we'll always use the default device.
        # TODO: Investigate ma_engine_config fields for noDevice mode

        result = lib.ma_engine_init(ffi.addressof(config), self._engine)
        _check_result(result, "Failed to initialize engine")
        self._initialized = True

    @property
    def sample_rate(self) -> int:
        """Get the engine's sample rate."""
        return lib.ma_engine_get_sample_rate(self._engine)

    def get_time_frames(self) -> int:
        """Get current engine time in PCM frames."""
        return lib.ma_engine_get_time_in_pcm_frames(self._engine)

    def get_time_seconds(self) -> float:
        """Get current engine time in seconds."""
        return self.get_time_frames() / self.sample_rate

    def set_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0+)."""
        lib.ma_engine_set_volume(self._engine, volume)

    def start(self) -> None:
        """Start the audio engine (usually auto-started)."""
        result = lib.ma_engine_start(self._engine)
        _check_result(result, "Failed to start engine")

    def stop(self) -> None:
        """Stop the audio engine."""
        result = lib.ma_engine_stop(self._engine)
        _check_result(result, "Failed to stop engine")

    def read_frames(self, frame_count: int) -> bytes:
        """
        Read audio frames from the engine (for testing/offline rendering).

        Returns raw PCM data as bytes (float32, stereo interleaved).
        """
        # Allocate buffer for float32 stereo frames
        buffer = ffi.new(f"float[{frame_count * self.CHANNELS}]")
        frames_read = ffi.new("ma_uint64*")

        result = lib.ma_engine_read_pcm_frames(
            self._engine, buffer, frame_count, frames_read
        )
        _check_result(result, "Failed to read PCM frames")

        # Convert to bytes
        actual_samples = int(frames_read[0]) * self.CHANNELS
        return ffi.buffer(buffer, actual_samples * 4)[:]

    def uninit(self) -> None:
        """Clean up engine resources."""
        if self._initialized:
            lib.ma_engine_uninit(self._engine)
            self._initialized = False

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        self.uninit()

    @property
    def _ptr(self):
        """Get the raw ma_engine pointer (for internal use)."""
        return self._engine
