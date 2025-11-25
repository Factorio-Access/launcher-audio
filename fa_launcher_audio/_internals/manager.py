"""AudioManager - main public interface."""

import json
from typing import Callable

from fa_launcher_audio._internals.engine import MiniaudioEngine
from fa_launcher_audio._internals.worker import CommandWorker


class AudioManager:
    """
    Main audio engine with context manager support.

    Usage:
        def data_provider(name: str) -> bytes:
            return Path(name).read_bytes()

        with AudioManager(data_provider=data_provider) as mgr:
            mgr.submit_command({
                "command": "patch",
                "id": "my_sound",
                "source": {"kind": "waveform", "waveform": "sine", "frequency": 440},
                "gains": {"overall": 0.5, "left": 1.0, "right": 1.0},
                "looping": False,
                "playback_rate": 1.0
            })
    """

    def __init__(self, data_provider: Callable[[str], bytes]):
        """
        Initialize audio manager.

        Args:
            data_provider: Callback that returns bytes for a given sound name.
        """
        self._data_provider = data_provider
        self._engine: MiniaudioEngine | None = None
        self._worker: CommandWorker | None = None

    def __enter__(self) -> "AudioManager":
        """Start the engine and background worker."""
        self._engine = MiniaudioEngine()
        self._worker = CommandWorker(self._engine, self._data_provider)
        self._worker.start()
        return self

    def __exit__(self, *args) -> None:
        """Immediately stop all sounds and cleanup."""
        if self._worker:
            self._worker.stop()
            self._worker = None
        if self._engine:
            self._engine.uninit()
            self._engine = None

    def submit_command(self, command: str | dict) -> None:
        """
        Submit a JSON command for processing.

        Args:
            command: JSON string or dict with command data.
                     Commands: "stop", "patch"
        """
        if self._worker is None:
            raise RuntimeError("AudioManager not started. Use as context manager.")

        if isinstance(command, dict):
            command = json.dumps(command)

        self._worker.submit(command)

    @property
    def engine(self) -> MiniaudioEngine | None:
        """Get the underlying engine (for advanced use)."""
        return self._engine
