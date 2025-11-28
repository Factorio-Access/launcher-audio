# fa_launcher_audio

Audio library for the Factorio Access mod launcher, wrapping miniaudio via CFFI with a declarative JSON command interface.

## What this Is

Factorio Access needs more audio than the engine supports, and it needs a way to get that audio to the user without losing access to the main thread.  Most Python libraries assume that the main thread is theirs to do with what they will.  On top of that, Factorio Access wants to call into this from Lua inside a process with only stdout available.  Similar mods are in similar situations--you've got thing inside the engine in some language, and it's not capable enough, so you wrap it in a launcher process.  If that launcher process is in Python, this package may be of help.

This package solves that problem by providing what at first appears to be an awkward interface.  You create a manager, attach your custom file reading logic, and then issue commands to it.  Those commands are all Python dicts in forms documented below.
Why is because you can go `json.loads(string)`.  So, for example in Factorio Access's case, the launcher receives prints over stdout like this:

```
acmd 5 { some json... }
```

Which is "do an audio command for player id 5, decoding this JSON".

What that means is that the Lua inside Factorio (or whatever you have in your case) can send commands directly to this package calling its API, without having to make your launcher know about everything this package can do.

This package never needs to talk in the other direction, not even to generate unique sound ids.  You generate those
however you want and start using them, and this goes "new sound!" and creates it.  You never have to figure out a
bidirectional channel in other words.  Since most implementations of modding have some way to get information out--even
if it just be normal print() statements--and often no way to get information back in, this should be widely applicable
to that case.

## What This Isn't

This package is not for general game dev.  The interface is terrible for that.  It's also not going to be on Pypi, and it doesn't guarantee long-term API compatibility, and it doesn't even guarantee version bumps.  If you need this package you know; if you don't, you want something else.
There are many more convenient options, such as pygame, for when you are able to hand over the main thread as one does in a typical application and are also in the position to call normal methods in the normal way.

## Installation (users)

We pin to Python 3.11 and we do not upload to Pypi.  This package is not designed for Pypi uploading, as it is a niche package for internal use of accessibility mods and does not come with compatible guarantees.

You need to be able to build Python C extensions, which requires a C compiler and (for non-Windows platforms) the Python*-dev packages.  This is too specific to your system for us to provide better documentation of how to do it.

After that, typically, you put this in requirements.txt:

```
fa_launcher_audio @ git+https://github.com/Factorio-Access/launcher-audio.git
```

And that's it.

If you are using UV, UV also supports adding from git.  We recommend UV for modern development when possible.

Do note that pip sometimes has trouble upgrading.  You must often use `--upgrade`.  If that does not work then remove
and reinstall this package.  See e.g. [this issue](https://github.com/pypa/pip/issues/2837).  UV should not have this
problem.

## Installation (development)

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) package manager.

```bash
# Clone with submodules
git clone --recurse-submodules <repo-url>
cd launcher-audio

# Install dependencies and build CFFI extension
uv sync
uv run python fa_launcher_audio/_internals/bindings/ffi_build.py
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

## Overview

This package works on sounds.  A sound consists of a source, and some parameters.  Sources include files and some synthetic waveforms with various options.  Parameters include pitch, pan, and volume.

A sound comes into existence by you making up an id however you want.  Factorio Access for example uses fixed constants some of the time, and incrementing counters for others.  Sounds go out of existence by finishing.  While a sound of a given id is playing, no second sound of that id can play.  So, you can for example spam the same sound 500 times and it will only play again after each finishes.  Instead, the overlapping ones patch the existing sound.
As a result, take Factorio's train direction tones.  We use a fixed id for those, so if a tone is already playing we move it/update it, and if a tone is not playing it starts again.

This supports two use cases well and one use case very poorly.  The two use cases it supports well are:

- You want to play a bunch of one-off sounds with fixed parameters: to do that generate a unique id and only ever emit one patch command per id
- You want to play the same sound and move it around: either set looping to true, or if you're fine with gaps because e.g. you're trying to make a tone go slower or faster based on a value keep issuing the same id.  This will play the sound up to as fast as its length, and no faster.

The use case that is poorly supported is reliably updating a sound without starting it again.  This is a reasonably
uncommon use case.  Small gauges and such are often just short one-off tones.  Enemy positions are usually a repeating
sound. For the Factorio use case, we do not anticipate much creating a long sound that's not looping and moving it and
reliably not starting it again, so that is not currently implemented functionality. If there is enough demand there are
obvious extensions to this package which would enable such usage, but they have other problems because of the overhead
of communicating with a launcher process in the first place--for example gaps due to latency in the print() commands,
even if the mod does issue them reliably. Do note that things that seem to work on high end or unloaded machines won't
work on low end or busy ones, so the obvious approaches for that are not at all applicable.  This package, in other
words, is limiting itself to the use cases that can be done reliably for the time being.
This is one reason you are better off with something else for normal games.  Creating a realistic environment when you cannot reliably move ongoing ambient sounds around is a challenge, but this package is for things like radars and the precise, unrealistic conveying of information.

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

Volume, pan, and pitch can be static values or time-based envelopes. Please note that time-based envelopes may be
removed in future, if we can't iron out some bugs.

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

One problem which can occur is that due to system glitches or other interruptions, sounds don't play reliably at the
right times.  Use `start_time` to schedule sounds for the future relative to "now":

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
- `ping_test.py` - Tests waveform ID reuse with repeated pings

Run examples with:

```bash
uv run python examples/play_file.py
```

## Development

### Running tests

```bash
uv run pytest
```

## License

zlib license. See [LICENSE](LICENSE) file.

Dependencies are all equally permissive or explicitly in the public domain.
