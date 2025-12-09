"""Sound class - wraps a data source with playback control."""

from typing import TYPE_CHECKING
from fa_launcher_audio._audio_cffi import ffi, lib
from fa_launcher_audio._internals.engine import _check_result

if TYPE_CHECKING:
    from fa_launcher_audio._internals.engine import MiniaudioEngine
    from fa_launcher_audio._internals.sources import WaveformSource, EncodedBytesSource

# Sound flags for custom node graph wiring
_SOUND_FLAGS = (
    lib.MA_SOUND_FLAG_NO_DEFAULT_ATTACHMENT |  # We'll wire manually
    lib.MA_SOUND_FLAG_NO_SPATIALIZATION        # Not using 3D audio
)

# Special value to keep sound output channel count matching data source
_SOUND_SOURCE_CHANNEL_COUNT = lib.MA_SOUND_SOURCE_CHANNEL_COUNT

# 50ms fade duration for smooth volume transitions (at 44100 Hz)
FADE_DURATION_FRAMES = 2205


class Sound:
    """
    A playable sound with volume, pitch, pan, looping, and optional LPF control.

    Wraps a data source (waveform, decoder, etc.) with ma_sound for playback.
    Uses a custom equal-power panner node (all sources are mono).

    When LPF is enabled, creates a dual signal path:
    - sound -> splitter -> panner (unfiltered) -> endpoint
    - sound -> splitter -> lpf_node -> panner_filtered -> endpoint

    The blend between paths is controlled by filter_gain.
    """

    def __init__(
        self,
        engine: "MiniaudioEngine",
        source: "WaveformSource | EncodedBytesSource",
        sound_id: str,
        lpf_cutoff: float | None = None,
    ):
        """
        Create a sound from a data source.

        Args:
            engine: The MiniaudioEngine instance
            source: The audio source (WaveformSource, EncodedBytesSource, etc.)
            sound_id: Unique identifier for this sound
            lpf_cutoff: If provided, creates a dual-path with LPF at this cutoff frequency
        """
        self._id = sound_id
        self._engine = engine
        self._source = source
        self._sound = ffi.new("ma_sound*")
        self._panner = ffi.new("panner_node*")
        self._initialized = False
        self._panner_initialized = False

        # LPF-related nodes (only used if lpf_cutoff is provided)
        self._has_lpf = lpf_cutoff is not None
        self._splitter = None
        self._lpf_node = None
        self._panner_filtered = None
        self._splitter_initialized = False
        self._lpf_initialized = False
        self._panner_filtered_initialized = False

        # Initialize ma_sound from the data source using advanced config
        # This allows us to control output channel count
        config = lib.ma_sound_config_init_2(engine._ptr)
        config.pDataSource = source.get_data_source_ptr()
        config.flags = _SOUND_FLAGS
        # Keep output channels matching data source (mono stays mono)
        config.channelsOut = _SOUND_SOURCE_CHANNEL_COUNT

        result = lib.ma_sound_init_ex(engine._ptr, ffi.addressof(config), self._sound)
        _check_result(result, f"Failed to initialize sound {sound_id}")
        self._initialized = True

        endpoint = lib.ma_engine_get_endpoint(engine._ptr)
        node_graph = lib.ma_engine_get_node_graph(engine._ptr)

        if self._has_lpf:
            # Dual-path routing with LPF
            # sound -> splitter -> [panner (unfiltered), lpf -> panner_filtered]
            self._splitter = ffi.new("ma_splitter_node*")
            self._lpf_node = ffi.new("ma_lpf_node*")
            self._panner_filtered = ffi.new("panner_node*")

            # Initialize splitter (mono, 2 outputs)
            splitter_config = lib.ma_splitter_node_config_init(1)  # 1 channel (mono)
            result = lib.ma_splitter_node_init(node_graph, ffi.addressof(splitter_config), ffi.NULL, self._splitter)
            _check_result(result, f"Failed to initialize splitter for sound {sound_id}")
            self._splitter_initialized = True

            # Initialize LPF node (mono, order 2 is a good default)
            sample_rate = lib.ma_engine_get_sample_rate(engine._ptr)
            lpf_config = lib.ma_lpf_node_config_init(1, sample_rate, lpf_cutoff, 2)
            result = lib.ma_lpf_node_init(node_graph, ffi.addressof(lpf_config), ffi.NULL, self._lpf_node)
            _check_result(result, f"Failed to initialize LPF for sound {sound_id}")
            self._lpf_initialized = True

            # Initialize unfiltered panner
            result = lib.panner_node_init(node_graph, 0.0, ffi.NULL, self._panner)
            _check_result(result, f"Failed to initialize panner for sound {sound_id}")
            self._panner_initialized = True

            # Initialize filtered panner
            result = lib.panner_node_init(node_graph, 0.0, ffi.NULL, self._panner_filtered)
            _check_result(result, f"Failed to initialize filtered panner for sound {sound_id}")
            self._panner_filtered_initialized = True

            # Wire: sound -> splitter
            result = lib.ma_node_attach_output_bus(self._sound, 0, self._splitter, 0)
            _check_result(result, f"Failed to attach sound to splitter for {sound_id}")

            # Wire: splitter output 0 -> panner (unfiltered path)
            result = lib.ma_node_attach_output_bus(self._splitter, 0, self._panner, 0)
            _check_result(result, f"Failed to attach splitter to panner for {sound_id}")

            # Wire: splitter output 1 -> lpf
            result = lib.ma_node_attach_output_bus(self._splitter, 1, self._lpf_node, 0)
            _check_result(result, f"Failed to attach splitter to LPF for {sound_id}")

            # Wire: lpf -> panner_filtered
            result = lib.ma_node_attach_output_bus(self._lpf_node, 0, self._panner_filtered, 0)
            _check_result(result, f"Failed to attach LPF to filtered panner for {sound_id}")

            # Wire: both panners -> endpoint
            result = lib.ma_node_attach_output_bus(self._panner, 0, endpoint, 0)
            _check_result(result, f"Failed to attach panner to endpoint for {sound_id}")

            result = lib.ma_node_attach_output_bus(self._panner_filtered, 0, endpoint, 0)
            _check_result(result, f"Failed to attach filtered panner to endpoint for {sound_id}")

        else:
            # Simple single-path routing (no LPF)
            # sound (mono) -> panner (mono->stereo) -> endpoint
            result = lib.panner_node_init(node_graph, 0.0, ffi.NULL, self._panner)
            _check_result(result, f"Failed to initialize panner for sound {sound_id}")
            self._panner_initialized = True

            # Wire: sound -> panner
            result = lib.ma_node_attach_output_bus(self._sound, 0, self._panner, 0)
            _check_result(result, f"Failed to attach sound to panner for {sound_id}")

            # Wire: panner -> endpoint
            result = lib.ma_node_attach_output_bus(self._panner, 0, endpoint, 0)
            _check_result(result, f"Failed to attach panner to endpoint for {sound_id}")

        # Track parameters
        self._volume = 1.0
        self._pan = 0.0
        self._pitch = 1.0
        self._looping = False
        self._started = False
        self._filter_gain = 1.0 if self._has_lpf else 0.0  # Default: full filter when LPF present

    @property
    def id(self) -> str:
        """Get the sound's unique identifier."""
        return self._id

    def set_volume(self, volume: float, use_fade: bool = True) -> None:
        """
        Set overall volume (0.0 to 2.0+).

        Uses ma_sound_set_fade for smooth 50ms transitions (thread-safe).
        The -1 value for volumeBeg means "use current volume".

        Args:
            volume: Target volume level
            use_fade: If True, fade over 50ms. If False, set instantly.
        """
        self._volume = volume
        if use_fade:
            # Use fade for smooth transition (-1 = current volume)
            lib.ma_sound_set_fade_in_pcm_frames(
                self._sound, -1.0, volume, FADE_DURATION_FRAMES
            )
        else:
            # Instant set via output bus volume (for initialization)
            lib.ma_node_set_output_bus_volume(self._sound, 0, volume)

    def set_pan(self, pan: float) -> None:
        """
        Set stereo pan position using equal-power panning.

        Args:
            pan: -1.0 (full left) to +1.0 (full right), 0.0 = center
        """
        self._pan = max(-1.0, min(1.0, pan))
        lib.panner_node_set_pan(self._panner, self._pan)
        # Also set pan on filtered panner if present
        if self._has_lpf and self._panner_filtered_initialized:
            lib.panner_node_set_pan(self._panner_filtered, self._pan)

    def set_filter_gain(self, filter_gain: float) -> None:
        """
        Set the blend between unfiltered and filtered signal.

        Only has effect when LPF is enabled for this sound.

        Args:
            filter_gain: 0.0 = fully unfiltered, 1.0 = fully filtered
        """
        if not self._has_lpf:
            return

        self._filter_gain = max(0.0, min(1.0, filter_gain))
        # Set output bus volumes on the panners to control the blend
        # Unfiltered gets (1 - filter_gain), filtered gets filter_gain
        lib.ma_node_set_output_bus_volume(self._panner, 0, 1.0 - self._filter_gain)
        lib.ma_node_set_output_bus_volume(self._panner_filtered, 0, self._filter_gain)

    @property
    def has_lpf(self) -> bool:
        """Check if this sound has LPF capability."""
        return self._has_lpf

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
        # Uninit downstream nodes first (reverse order of the graph)

        # Uninit filtered panner (if present)
        if self._panner_filtered_initialized:
            lib.panner_node_uninit(self._panner_filtered, ffi.NULL)
            self._panner_filtered_initialized = False

        # Uninit unfiltered panner
        if self._panner_initialized:
            lib.panner_node_uninit(self._panner, ffi.NULL)
            self._panner_initialized = False

        # Uninit LPF node (if present)
        if self._lpf_initialized:
            lib.ma_lpf_node_uninit(self._lpf_node, ffi.NULL)
            self._lpf_initialized = False

        # Uninit splitter (if present)
        if self._splitter_initialized:
            lib.ma_splitter_node_uninit(self._splitter, ffi.NULL)
            self._splitter_initialized = False

        # Uninit sound
        if self._initialized:
            lib.ma_sound_uninit(self._sound)
            self._initialized = False

        # Also cleanup the source
        if self._source:
            self._source.cleanup()
            self._source = None

    def __del__(self):
        self.cleanup()
