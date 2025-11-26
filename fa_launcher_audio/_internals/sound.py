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
        self._volume = 1.0
        self._pan = 0.0
        self._pitch = 1.0
        self._looping = False
        self._started = False

    @property
    def id(self) -> str:
        """Get the sound's unique identifier."""
        return self._id

    def set_volume(self, volume: float) -> None:
        """
        Set overall volume (0.0 to 2.0+).

        Uses ma_node_set_output_bus_volume which is separate from the
        internal fader, allowing fades to work independently.
        """
        self._volume = volume
        # Use node output bus volume - separate from the fader
        lib.ma_node_set_output_bus_volume(self._sound, 0, volume)

    def set_pan(self, pan: float) -> None:
        """
        Set stereo pan position.

        Args:
            pan: -1.0 (full left) to +1.0 (full right), 0.0 = center
        """
        self._pan = max(-1.0, min(1.0, pan))
        lib.ma_sound_set_pan(self._sound, self._pan)

    def set_pitch(self, pitch: float) -> None:
        """Set playback rate/pitch (0.5 to 2.0)."""
        self._pitch = pitch
        lib.ma_sound_set_pitch(self._sound, pitch)

    def set_looping(self, looping: bool) -> None:
        """Set whether the sound loops."""
        self._looping = looping
        lib.ma_sound_set_looping(self._sound, 1 if looping else 0)

    def start(self) -> None:
        """Start playback."""
        if not self._started:
            result = lib.ma_sound_start(self._sound)
            _check_result(result, f"Failed to start sound {self._id}")
            self._started = True

    def stop(self) -> None:
        """Stop playback immediately."""
        result = lib.ma_sound_stop(self._sound)
        _check_result(result, f"Failed to stop sound {self._id}")

    def is_playing(self) -> bool:
        """Check if the sound is currently playing."""
        return bool(lib.ma_sound_is_playing(self._sound))

    def is_at_end(self) -> bool:
        """Check if the sound has reached the end."""
        return bool(lib.ma_sound_at_end(self._sound))

    def is_finished(self) -> bool:
        """Check if the sound is finished (not looping and at end, or stopped)."""
        if self._looping:
            return False
        return self.is_at_end()

    def seek(self, frame_index: int) -> None:
        """Seek to a specific frame position."""
        result = lib.ma_sound_seek_to_pcm_frame(self._sound, frame_index)
        _check_result(result, f"Failed to seek sound {self._id}")

    def set_fade(
        self, volume_start: float, volume_end: float, duration_frames: int
    ) -> None:
        """Set a fade effect starting immediately."""
        lib.ma_sound_set_fade_in_pcm_frames(
            self._sound, volume_start, volume_end, duration_frames
        )

    def set_fade_at(
        self,
        volume_start: float,
        volume_end: float,
        duration_frames: int,
        start_frame: int,
    ) -> None:
        """Schedule a fade effect to start at a specific engine time."""
        lib.ma_sound_set_fade_start_in_pcm_frames(
            self._sound, volume_start, volume_end, duration_frames, start_frame
        )

    def schedule_start(self, absolute_frame: int) -> None:
        """Schedule the sound to start at a specific engine time."""
        lib.ma_sound_set_start_time_in_pcm_frames(self._sound, absolute_frame)

    def schedule_stop(self, absolute_frame: int) -> None:
        """Schedule the sound to stop at a specific engine time."""
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
