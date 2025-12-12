"""Background worker thread for command processing."""

import queue
import threading
import time

from fa_launcher_audio._internals.cache import BytesCache
from fa_launcher_audio._internals.engine import MiniaudioEngine
from fa_launcher_audio._internals.sound import Sound
from fa_launcher_audio._internals.sources import WaveformSource, DecoderSource
from fa_launcher_audio._internals.commands import (
    parse_command,
    PatchCommand,
    StopCommand,
    CompoundCommand,
    LpfConfig,
    validate_command,
)
from fa_launcher_audio._internals.parameters import VolumeParams, Parameter, StaticParam


SAMPLE_RATE = 44100


class ManagedSound:
    """A sound with its associated parameters for updating."""

    def __init__(
        self,
        sound: Sound,
        volume_params: VolumeParams,
        playback_rate: Parameter,
        start_time: float,
        duration: float | None = None,
        scheduled: bool = False,
        scheduled_stop_frame: int | None = None,
        filter_gain: Parameter | None = None,
    ):
        self.sound = sound
        self.volume_params = volume_params
        self.playback_rate = playback_rate
        self.start_time = start_time  # Engine time when sound becomes active
        self.duration = duration  # None means play until natural end
        self.scheduled = scheduled  # True if waiting for scheduled start
        self.scheduled_stop_frame = scheduled_stop_frame  # Frame when sound will stop (miniaudio clock)
        self.stopped_by_duration = False
        self.filter_gain = filter_gain  # Only used when sound has LPF
        # Track if this is the first update (for initial instant set vs fade)
        self._first_update = True

    def update(self, current_time: float) -> None:
        """Update sound parameters based on current time."""
        # If scheduled and not yet playing, check if it's started
        if self.scheduled:
            if self.sound.is_playing():
                self.scheduled = False
            else:
                return  # Not started yet, skip updates

        elapsed = current_time - self.start_time

        # Check if duration exceeded
        if self.duration is not None and not self.stopped_by_duration:
            if elapsed >= self.duration:
                self.sound.stop()
                self.stopped_by_duration = True
                return

        # Update volume and pan
        # Volume now uses 50ms fades for smooth transitions (except first update)
        volume, pan = self.volume_params.get_values(elapsed)
        self.sound.set_volume(volume, use_fade=not self._first_update)
        self.sound.set_pan(pan)

        # Update pitch
        pitch = self.playback_rate.get_value(elapsed)
        self.sound.set_pitch(pitch)

        # Update filter gain if this sound has LPF
        if self.filter_gain is not None and self.sound.has_lpf:
            fg = self.filter_gain.get_value(elapsed)
            self.sound.set_filter_gain(fg)

        self._first_update = False

    def is_finished(self, current_frame: int) -> bool:
        """Check if the sound is finished (either naturally or by duration or scheduled stop)."""
        if self.stopped_by_duration:
            return True
        if self.scheduled_stop_frame is not None and current_frame >= self.scheduled_stop_frame:
            return True
        return self.sound.is_finished()


class CommandWorker:
    """
    Background thread that processes commands and updates sounds.

    Runs a loop that:
    1. Processes queued commands
    2. Updates time-based parameters on active sounds
    3. Removes finished sounds
    """

    UPDATE_INTERVAL = 0.01  # 10ms tick

    def __init__(
        self,
        engine: MiniaudioEngine,
        bytes_cache: BytesCache,
    ):
        self._engine = engine
        self._bytes_cache = bytes_cache
        self._sounds: dict[str, ManagedSound] = {}
        self._queue: queue.Queue[str | dict] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker thread and cleanup all sounds."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Cleanup all sounds
        for managed in self._sounds.values():
            managed.sound.cleanup()
        self._sounds.clear()

    def submit(self, command: str | dict) -> None:
        """Queue a command for processing."""
        self._queue.put(command)

    def _run(self) -> None:
        """Worker thread main loop."""
        while self._running:
            # Wait for command or timeout
            try:
                cmd_data = self._queue.get(timeout=self.UPDATE_INTERVAL)
                self._process_single_command(cmd_data)
                # Drain any additional queued commands
                self._process_commands()
            except queue.Empty:
                pass  # Timeout - just continue to updates

            # Update active sounds
            self._update_sounds()

            # Remove finished sounds
            self._cleanup_finished()

    def _process_single_command(self, cmd_data: str | dict) -> None:
        """Process a single command."""
        cmd = parse_command(cmd_data)
        errors = validate_command(cmd)
        if errors:
            raise ValueError(f"Command validation errors: {errors}")

        self._execute_command(cmd)

    def _process_commands(self) -> None:
        """Process all pending commands."""
        while True:
            try:
                cmd_data = self._queue.get_nowait()
            except queue.Empty:
                break

            self._process_single_command(cmd_data)

    def _execute_command(self, cmd: PatchCommand | StopCommand | CompoundCommand) -> None:
        """Execute a parsed command."""
        if isinstance(cmd, StopCommand):
            self._handle_stop(cmd)
        elif isinstance(cmd, PatchCommand):
            self._handle_patch(cmd)
        elif isinstance(cmd, CompoundCommand):
            for sub_cmd in cmd.commands:
                self._execute_command(sub_cmd)

    def _handle_stop(self, cmd: StopCommand) -> None:
        """Handle a stop command."""
        if cmd.id in self._sounds:
            managed = self._sounds.pop(cmd.id)
            managed.sound.stop()
            managed.sound.cleanup()

    def _handle_patch(self, cmd: PatchCommand) -> None:
        """Handle a patch command."""
        # If sound exists, update it; otherwise create it
        if cmd.id in self._sounds:
            self._update_existing_sound(cmd)
        else:
            self._create_new_sound(cmd)

    def _create_new_sound(self, cmd: PatchCommand) -> None:
        """Create a new sound from a patch command."""
        source = self._create_source(cmd.source)
        if source is None:
            return

        # Determine LPF cutoff (None if no LPF)
        lpf_cutoff = None
        if cmd.lpf is not None:
            lpf_cutoff = cmd.lpf.cutoff

        # Get initial pan to avoid fade from center on first frame
        initial_volume, initial_pan = cmd.volume_params.get_values(0.0)

        sound = Sound(self._engine, source, cmd.id, lpf_cutoff=lpf_cutoff, initial_pan=initial_pan)
        sound.set_looping(cmd.looping)

        # Apply initial parameters (use_fade=False for instant initial set)
        sound.set_volume(initial_volume, use_fade=False)
        sound.set_pitch(cmd.playback_rate.get_value(0.0))

        # Apply initial filter gain if LPF is present
        if cmd.filter_gain is not None and sound.has_lpf:
            sound.set_filter_gain(cmd.filter_gain.get_value(0.0))

        current_time = self._engine.get_time_seconds()
        current_frame = self._engine.get_time_frames()

        # Get duration from waveform source if available (and not looping)
        duration = None
        if not cmd.looping and cmd.source.kind == "waveform" and cmd.source.non_looping_duration:
            duration = cmd.source.non_looping_duration

        # Handle scheduled start
        scheduled = False
        scheduled_stop_frame = None
        if cmd.start_time > 0:
            start_frame = current_frame + int(cmd.start_time * SAMPLE_RATE)
            sound.schedule_start(start_frame)

            # Schedule fade-out if waveform has fade_out and duration
            # Use -1 for start volume (current volume) since volume is controlled
            # via node bus, not the internal fader
            if cmd.source.kind == "waveform" and cmd.source.fade_out and duration:
                fade_out_frames = int(cmd.source.fade_out * SAMPLE_RATE)
                scheduled_stop_frame = start_frame + int(duration * SAMPLE_RATE)
                fade_out_start_frame = scheduled_stop_frame - fade_out_frames
                sound.set_fade_at(-1.0, 0.0, fade_out_frames, fade_out_start_frame)

                # Schedule stop at end
                sound.schedule_stop(scheduled_stop_frame)

            sound.start()
            scheduled = True
            start_time = current_time + cmd.start_time
        else:
            # Immediate start
            # Schedule fade-out if waveform has fade_out and duration
            # Use -1 for start volume (current volume) since volume is controlled
            # via node bus, not the internal fader
            if cmd.source.kind == "waveform" and cmd.source.fade_out and duration:
                fade_out_frames = int(cmd.source.fade_out * SAMPLE_RATE)
                scheduled_stop_frame = current_frame + int(duration * SAMPLE_RATE)
                fade_out_start_frame = scheduled_stop_frame - fade_out_frames
                sound.set_fade_at(-1.0, 0.0, fade_out_frames, fade_out_start_frame)

                # Schedule stop at end
                sound.schedule_stop(scheduled_stop_frame)

            sound.start()
            start_time = current_time

        # Track for updates
        managed = ManagedSound(
            sound=sound,
            volume_params=cmd.volume_params,
            playback_rate=cmd.playback_rate,
            start_time=start_time,
            duration=duration if not scheduled_stop_frame else None,  # Don't use duration stop if scheduled stop handles it
            scheduled=scheduled,
            scheduled_stop_frame=scheduled_stop_frame,
            filter_gain=cmd.filter_gain,
        )
        self._sounds[cmd.id] = managed

    def _update_existing_sound(self, cmd: PatchCommand) -> None:
        """Update an existing sound's parameters."""
        managed = self._sounds[cmd.id]

        # Update looping (can only go true -> false per spec)
        if not cmd.looping:
            managed.sound.set_looping(False)

        # Update parameter sources for future updates
        managed.volume_params = cmd.volume_params
        managed.playback_rate = cmd.playback_rate

        # Update filter_gain if present (LPF config itself is immutable)
        if cmd.filter_gain is not None:
            managed.filter_gain = cmd.filter_gain

        # Note: We don't reset start_time, so parameters continue from
        # the original creation time. This matches the declarative model
        # where volume/pan/pitch are relative to sound start.

    def _create_source(self, source_config) -> WaveformSource | DecoderSource | None:
        """Create a source from configuration."""
        if source_config.kind == "waveform":
            return WaveformSource(
                waveform_type=source_config.waveform,
                frequency=source_config.frequency,
                duration_seconds=source_config.non_looping_duration,
            )

        elif source_config.kind == "encoded_bytes":
            audio_bytes = self._bytes_cache.get(source_config.name)
            return DecoderSource(audio_bytes)

        return None

    def _update_sounds(self) -> None:
        """Update all active sounds with time-based parameters and duration."""
        current_time = self._engine.get_time_seconds()

        for managed in self._sounds.values():
            # Always update (handles duration checking even if params are constant)
            managed.update(current_time)

    def _cleanup_finished(self) -> None:
        """Remove finished sounds."""
        current_frame = self._engine.get_time_frames()
        finished_ids = [
            sid for sid, managed in self._sounds.items()
            if managed.is_finished(current_frame)
        ]

        for sid in finished_ids:
            managed = self._sounds.pop(sid)
            managed.sound.cleanup()
