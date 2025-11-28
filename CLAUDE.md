# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
uv sync

# Build CFFI extension (required after changing audio_defs.h or ffi_build.py)
uv run python fa_launcher_audio/_internals/bindings/ffi_build.py

# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/test_commands.py

# Run specific test
uv run pytest tests/test_commands.py::TestParseCommand::test_parse_patch_waveform

# Build wheel
uv run python -m build --wheel
```

If the `.pyd` file is locked during rebuild, delete it manually then rebuild.  If you cannot delete it manually, ask the user to assist.

## Architecture

This library wraps miniaudio via CFFI with a declarative JSON command interface. The main components:

### CFFI Layer (`_internals/bindings/`)
- `audio_defs.h` - Declares miniaudio functions/types exposed to Python
- `ffi_build.py` - Compiles the CFFI extension with release flags (`-O2 -DNDEBUG`)
- Headers (miniaudio.h, dr_*.h, stb_vorbis.c) are in `fa_launcher_audio/` root

### Core Classes
- `MiniaudioEngine` (`engine.py`) - Wraps `ma_engine`, provides time tracking
- `Sound` (`sound.py`) - Wraps `ma_sound` with volume (via `ma_node_set_output_bus_volume`), pan, pitch, fade control
- `WaveformSource`, `EncodedBytesSource`, `DecoderSource` (`sources.py`) - Audio data sources

### Command Processing
- `commands.py` - Parses/validates JSON commands (`patch`, `stop`, `compound`)
- `parameters.py` - `VolumeParams` (volume + pan), `TimeEnvelope` for interpolated values
- `worker.py` - Background thread processes commands, updates sounds. Uses `Queue.get(timeout=)` to wake immediately on new commands
- `manager.py` - Public `AudioManager` API, owns engine and worker

### Key Design Decisions
- **Volume separate from fader**: `ma_node_set_output_bus_volume` controls volume independently, so fades use `-1` (current volume) as start value
- **All timing is absolute**: Worker loop uses engine time, not tick counting, so variable loop intervals are safe
- **`_initialized` pattern**: Only checked in cleanup/uninit methods since `__init__` throws on failure
- **No Python callbacks on audio thread**: GIL prevents this; all audio processing is in C
