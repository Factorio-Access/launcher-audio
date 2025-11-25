"""Background worker thread for command processing."""

import queue
import threading
import time
from typing import Callable

from fa_launcher_audio._internals.engine import MiniaudioEngine
from fa_launcher_audio._internals.sound import Sound
from fa_launcher_audio._internals.sources import WaveformSource, EncodedBytesSource
from fa_launcher_audio._internals.commands import (
    parse_command,
    PatchCommand,
    StopCommand,
    validate_command,
)
from fa_launcher_audio._internals.parameters import GainParams, Parameter


class ManagedSound:
    """A sound with its associated parameters for updating."""

    def __init__(
        self,
        sound: Sound,
        gains: GainParams,
        playback_rate: Parameter,
        start_time: float,
    ):
        self.sound = sound
        self.gains = gains
        self.playback_rate = playback_rate
        self.start_time = start_time  # Engine time when sound was created

    def update(self, current_time: float) -> None:
        """Update sound parameters based on current time."""
        elapsed = current_time - self.start_time

        # Update gains
        overall, left, right = self.gains.get_values(elapsed)
        self.sound.set_overall_gain(overall)
        self.sound.set_channel_gains(left, right)

        # Update pitch
        pitch = self.playback_rate.get_value(elapsed)
        self.sound.set_pitch(pitch)


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
        bytes_callback: Callable[[str], bytes],
    ):
        self._engine = engine
        self._bytes_callback = bytes_callback
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
            # Process all queued commands
            self._process_commands()

            # Update active sounds
            self._update_sounds()

            # Remove finished sounds
            self._cleanup_finished()

            # Sleep until next tick
            time.sleep(self.UPDATE_INTERVAL)

    def _process_commands(self) -> None:
        """Process all pending commands."""
        while True:
            try:
                cmd_data = self._queue.get_nowait()
            except queue.Empty:
                break

            try:
                cmd = parse_command(cmd_data)
                errors = validate_command(cmd)
                if errors:
                    # Log errors but continue
                    print(f"Command validation errors: {errors}")
                    continue

                self._execute_command(cmd)
            except Exception as e:
                # Log exception but don't crash worker
                print(f"Error processing command: {e}")

    def _execute_command(self, cmd: PatchCommand | StopCommand) -> None:
        """Execute a parsed command."""
        if isinstance(cmd, StopCommand):
            self._handle_stop(cmd)
        elif isinstance(cmd, PatchCommand):
            self._handle_patch(cmd)

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

        sound = Sound(self._engine, source, cmd.id)
        sound.set_looping(cmd.looping)

        # Apply initial parameters
        overall, left, right = cmd.gains.get_values(0.0)
        sound.set_overall_gain(overall)
        sound.set_channel_gains(left, right)
        sound.set_pitch(cmd.playback_rate.get_value(0.0))

        # Start the sound
        sound.start()

        # Track for updates
        current_time = self._engine.get_time_seconds()
        managed = ManagedSound(
            sound=sound,
            gains=cmd.gains,
            playback_rate=cmd.playback_rate,
            start_time=current_time,
        )
        self._sounds[cmd.id] = managed

    def _update_existing_sound(self, cmd: PatchCommand) -> None:
        """Update an existing sound's parameters."""
        managed = self._sounds[cmd.id]

        # Update looping (can only go true -> false per spec)
        if not cmd.looping:
            managed.sound.set_looping(False)

        # Update parameter sources for future updates
        managed.gains = cmd.gains
        managed.playback_rate = cmd.playback_rate

        # Note: We don't reset start_time, so parameters continue from
        # the original creation time. This matches the declarative model
        # where gains/pitch are relative to sound start.

    def _create_source(self, source_config) -> WaveformSource | EncodedBytesSource | None:
        """Create a source from configuration."""
        if source_config.kind == "waveform":
            return WaveformSource(
                waveform_type=source_config.waveform,
                frequency=source_config.frequency,
                duration_seconds=source_config.non_looping_duration,
            )

        elif source_config.kind == "encoded_bytes":
            return EncodedBytesSource(
                name=source_config.name,
                bytes_callback=self._bytes_callback,
            )

        elif source_config.kind == "timeline":
            # TODO: Implement timeline
            print("Timeline not yet implemented")
            return None

        return None

    def _update_sounds(self) -> None:
        """Update all active sounds with time-based parameters."""
        current_time = self._engine.get_time_seconds()

        for managed in self._sounds.values():
            # Only update if parameters are not constant
            if not managed.gains.is_constant() or not managed.playback_rate.is_constant():
                managed.update(current_time)

    def _cleanup_finished(self) -> None:
        """Remove finished sounds."""
        finished_ids = [
            sid for sid, managed in self._sounds.items()
            if managed.sound.is_finished()
        ]

        for sid in finished_ids:
            managed = self._sounds.pop(sid)
            managed.sound.cleanup()
