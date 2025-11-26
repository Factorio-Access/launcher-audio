# fa_launcher_audio

Audio library for the Factorio Access mod launcher, wrapping miniaudio via CFFI with a declarative JSON command interface.

## Features

- **Declarative API**: Tell the system "what is the case" rather than issuing imperative commands
- **JSON Commands**: Simple `patch`, `stop`, and `compound` commands for managing sounds
- **Audio Sources**:
  - `encoded_bytes`: Load audio files (WAV, FLAC, MP3, OGG) - downmixed to mono
  - `waveform`: Generate sine, square, triangle, or sawtooth waves with optional fade-out
- **Volume and pan control**: Independent volume and stereo panning
- **Time-based parameters**: Interpolate values over time (linear or instant)
- **Scheduled playback**: Use `start_time` to schedule sounds for future playback
- **Compound commands**: Batch multiple commands together

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) package manager.

```bash
# Clone with submodules
git clone --recurse-submodules <repo-url>
cd launcher-audio

# Install dependencies and build CFFI extension
uv sync
```

## Quick Start

```python
from fa_launcher_audio import AudioManager

def data_provider(name: str) -> bytes:
    """Load audio file bytes by name."""
    with open(name, "rb") as f:
        return f.read()

with AudioManager(data_provider=data_provider) as mgr:
    # Play an audio file
    mgr.submit_command({
        "command": "patch",
        "id": "music",
        "source": {"kind": "encoded_bytes", "name": "music.flac"},
        "volume": 0.5,
        "pan": 0.0,
        "looping": False,
        "playback_rate": 1.0,
    })

    # ... do other things ...

    # Stop the sound
    mgr.submit_command({
        "command": "stop",
        "id": "music",
    })
```

## Commands

### patch

Creates a new sound or updates an existing one. The declarative design means you describe the desired state, not actions to take.

```python
{
    "command": "patch",
    "id": "sound_id",           # Unique identifier
    "source": { ... },          # Audio source (see below)
    "volume": 1.0,              # Volume 0.0 to 2.0+ (default 1.0)
    "pan": 0.0,                 # Stereo pan -1.0 (left) to +1.0 (right)
    "looping": True/False,      # Whether to loop
    "playback_rate": 1.0,       # Pitch/speed (1.0 = normal)
    "start_time": 0.0,          # Seconds from now to start (0 = immediate)
}
```

### stop

Immediately stops and removes a sound.

```python
{
    "command": "stop",
    "id": "sound_id",
}
```

### compound

Execute multiple commands together. Useful for scheduling multiple sounds at specific times.

```python
{
    "command": "compound",
    "commands": [
        {"command": "patch", "id": "note1", "start_time": 0.0, "source": {...}},
        {"command": "patch", "id": "note2", "start_time": 0.5, "source": {...}},
    ],
}
```

## Audio Sources

### encoded_bytes

Plays audio from encoded file data (WAV, FLAC, MP3, OGG).

```python
"source": {
    "kind": "encoded_bytes",
    "name": "path/to/file.flac",  # Passed to data_provider callback
}
```

### waveform

Generates a waveform signal with optional fade-out for smooth endings.

```python
"source": {
    "kind": "waveform",
    "waveform": "sine",           # sine, square, triangle, saw
    "frequency": 440,             # Hz
    "non_looping_duration": 1.0,  # Duration in seconds (ignored if looping)
    "fade_out": 0.05,             # Fade out duration in seconds (optional)
}
```

## Volume, Pan, and Time-based Parameters

Volume and pan can be static values or time-based envelopes:

### Static values

```python
"volume": 0.5,
"pan": 0.0,
```

### Time-based envelope

```python
"volume": [
    {"time": 0.0, "value": 0.0, "interpolation_from_prev": "linear"},
    {"time": 0.5, "value": 1.0, "interpolation_from_prev": "linear"},
    {"time": 2.0, "value": 0.0, "interpolation_from_prev": "linear"},
],
"pan": [
    {"time": 0.0, "value": -1.0, "interpolation_from_prev": "linear"},
    {"time": 2.0, "value": 1.0, "interpolation_from_prev": "linear"},
],
```

Interpolation types:
- `"linear"`: Smooth transition from previous value
- `"jump"`: Instant change at the specified time

## Scheduled Playback

Use `start_time` to schedule sounds for the future:

```python
# Play a melody with scheduled notes
mgr.submit_command({
    "command": "compound",
    "commands": [
        {
            "command": "patch",
            "id": "note_0",
            "start_time": 0.0,
            "source": {"kind": "waveform", "waveform": "sine", "frequency": 261.63,
                       "non_looping_duration": 0.4, "fade_out": 0.05},
            "volume": 0.3,
        },
        {
            "command": "patch",
            "id": "note_1",
            "start_time": 0.5,
            "source": {"kind": "waveform", "waveform": "sine", "frequency": 293.66,
                       "non_looping_duration": 0.4, "fade_out": 0.05},
            "volume": 0.3,
        },
    ],
})
```

## Looping and Graceful Stop

To stop a looping sound gracefully (let it finish the current iteration):

```python
# Change looping to false - sound finishes current playthrough
mgr.submit_command({
    "command": "patch",
    "id": "music",
    "source": { ... },
    "volume": 0.5,
    "looping": False,  # Will stop after current iteration
    "playback_rate": 1.0,
})
```

For immediate stop, use the `stop` command.

## Examples

See the `examples/` directory:

- `play_file.py` - Basic file playback
- `panning_demo.py` - Pan from left to right using time-based pan envelope
- `timeline_song.py` - Simple melody using compound command with scheduled notes
- `looping_demo.py` - Looping and graceful stop demonstration

Run examples with:

```bash
uv run python examples/play_file.py
```

## Development

### Running tests

```bash
uv run pytest
```

### Project structure

```
fa_launcher_audio/
├── __init__.py              # Public API (AudioManager)
├── _internals/
│   ├── bindings/
│   │   ├── audio_defs.h     # CFFI declarations
│   │   ├── ffi_build.py     # CFFI build script
│   │   ├── miniaudio.h      # miniaudio header
│   │   └── dr_*.h           # dr_libs headers
│   ├── engine.py            # MiniaudioEngine wrapper
│   ├── sources.py           # WaveformSource, DecoderSource
│   ├── sound.py             # Sound class
│   ├── parameters.py        # Time-based parameter system
│   ├── commands.py          # Command parsing
│   ├── worker.py            # Background command processor
│   └── manager.py           # AudioManager implementation
```

## License

See LICENSE file.
