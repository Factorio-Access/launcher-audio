"""Sound class - wraps a data source with playback control."""

from typing import TYPE_CHECKING
from fa_launcher_audio._audio_cffi import ffi, lib
from fa_launcher_audio._internals.engine import _check_result

if TYPE_CHECKING:
    from fa_launcher_audio._internals.engine import MiniaudioEngine
    from fa_launcher_audio._internals.sources import WaveformSource, EncodedBytesSource


class Sound:
    """
    A playable sound with volume, pitch, pan, and looping control.

    Wraps a data source (waveform, decoder, etc.) with ma_sound for playback.
    """

    def __init__(
        self,
        engine: "MiniaudioEngine",
        source: "WaveformSource | EncodedBytesSource",
        sound_id: str,
    ):
        """
        Create a sound from a data source.

        Args:
            engine: The MiniaudioEngine instance
            source: The audio source (WaveformSource, EncodedBytesSource, etc.)
            sound_id: Unique identifier for this sound
        """
        self._id = sound_id
        self._engine = engine
        self._source = source
        self._sound = ffi.new("ma_sound*")
        self._initialized = False

        # Initialize ma_sound from the data source
        result = lib.ma_sound_init_from_data_source(
            engine._ptr,
            source.get_data_source_ptr(),
            0,  # flags
            ffi.NULL,  # pGroup
            self._sound,
        )
        _check_result(result, f"Failed to initialize sound {sound_id}")
        self._initialized = True

        # Track parameters
        self._overall_gain = 1.0
        self._left_gain = 1.0
        self._right_gain = 1.0
        self._pitch = 1.0
        self._looping = False
        self._started = False

    @property
    def id(self) -> str:
        """Get the sound's unique identifier."""
        return self._id

    def set_overall_gain(self, gain: float) -> None:
        """Set overall volume (0.0 to 2.0+)."""
        self._overall_gain = gain
        self._apply_gains()

    def set_channel_gains(self, left: float, right: float) -> None:
        """
        Set independent left/right channel gains.

        Note: This is implemented via pan approximation since ma_sound
        doesn't directly support per-channel gains. For precise control,
        we'd need a custom node graph setup.
        """
        self._left_gain = left
        self._right_gain = right
        self._apply_gains()

    def _apply_gains(self) -> None:
        """Apply the current gain settings to the sound."""
        if not self._initialized:
            return

        # Calculate effective gains
        left_eff = self._overall_gain * self._left_gain
        right_eff = self._overall_gain * self._right_gain

        # Use volume for the average, pan for the balance
        # Volume = average of L/R gains
        # Pan = -1 (full left) to +1 (full right)
        avg_gain = (left_eff + right_eff) / 2.0
        lib.ma_sound_set_volume(self._sound, avg_gain)

        # Pan: compute balance
        # If L > R, pan left (negative). If R > L, pan right (positive).
        total = left_eff + right_eff
        if total > 0.0001:
            # Pan range: -1 to +1
            # When left_eff == right_eff, pan = 0
            # When left_eff = 1, right_eff = 0, pan = -1
            # When left_eff = 0, right_eff = 1, pan = +1
            pan = (right_eff - left_eff) / total
            lib.ma_sound_set_pan(self._sound, pan)
        else:
            lib.ma_sound_set_pan(self._sound, 0.0)

    def set_pitch(self, pitch: float) -> None:
        """Set playback rate/pitch (0.5 to 2.0)."""
        self._pitch = pitch
        if self._initialized:
            lib.ma_sound_set_pitch(self._sound, pitch)

    def set_looping(self, looping: bool) -> None:
        """Set whether the sound loops."""
        self._looping = looping
        if self._initialized:
            lib.ma_sound_set_looping(self._sound, 1 if looping else 0)

    def start(self) -> None:
        """Start playback."""
        if self._initialized and not self._started:
            result = lib.ma_sound_start(self._sound)
            _check_result(result, f"Failed to start sound {self._id}")
            self._started = True

    def stop(self) -> None:
        """Stop playback immediately."""
        if self._initialized:
            result = lib.ma_sound_stop(self._sound)
            _check_result(result, f"Failed to stop sound {self._id}")

    def is_playing(self) -> bool:
        """Check if the sound is currently playing."""
        if not self._initialized:
            return False
        return bool(lib.ma_sound_is_playing(self._sound))

    def is_at_end(self) -> bool:
        """Check if the sound has reached the end."""
        if not self._initialized:
            return True
        return bool(lib.ma_sound_at_end(self._sound))

    def is_finished(self) -> bool:
        """Check if the sound is finished (not looping and at end, or stopped)."""
        if not self._initialized:
            return True
        if self._looping:
            return False
        return self.is_at_end()

    def seek(self, frame_index: int) -> None:
        """Seek to a specific frame position."""
        if self._initialized:
            result = lib.ma_sound_seek_to_pcm_frame(self._sound, frame_index)
            _check_result(result, f"Failed to seek sound {self._id}")

    def set_fade(
        self, volume_start: float, volume_end: float, duration_frames: int
    ) -> None:
        """Set a fade effect."""
        if self._initialized:
            lib.ma_sound_set_fade_in_pcm_frames(
                self._sound, volume_start, volume_end, duration_frames
            )

    def schedule_start(self, absolute_frame: int) -> None:
        """Schedule the sound to start at a specific engine time."""
        if self._initialized:
            lib.ma_sound_set_start_time_in_pcm_frames(self._sound, absolute_frame)

    def schedule_stop(self, absolute_frame: int) -> None:
        """Schedule the sound to stop at a specific engine time."""
        if self._initialized:
            lib.ma_sound_set_stop_time_in_pcm_frames(self._sound, absolute_frame)

    def cleanup(self) -> None:
        """Release sound resources."""
        if self._initialized:
            lib.ma_sound_uninit(self._sound)
            self._initialized = False

        # Also cleanup the source
        if self._source:
            self._source.cleanup()
            self._source = None

    def __del__(self):
        self.cleanup()
