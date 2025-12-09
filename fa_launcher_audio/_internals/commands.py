"""JSON command parsing for the audio system."""

import json
from dataclasses import dataclass
from typing import Literal

from fa_launcher_audio._internals.parameters import (
    VolumeParams,
    Parameter,
    parse_param,
)


@dataclass
class StopCommand:
    """Command to stop a sound."""

    id: str


@dataclass
class LpfConfig:
    """Configuration for low-pass filter."""

    cutoff: float  # Cutoff frequency in Hz
    enabled: bool  # Whether the filter is active


@dataclass
class SourceConfig:
    """Configuration for a sound source."""

    kind: Literal["encoded_bytes", "waveform"]
    # For encoded_bytes:
    name: str | None = None
    # For waveform:
    waveform: str | None = None  # sine, square, triangle, saw
    frequency: float | None = None
    non_looping_duration: float | None = None
    fade_out: float | None = None  # Fade out duration in seconds (waveform only)


@dataclass
class PatchCommand:
    """Command to create or update a sound."""

    id: str
    source: SourceConfig
    volume_params: VolumeParams
    looping: bool
    playback_rate: Parameter
    start_time: float = 0.0  # When to start (seconds from now), 0 = immediate
    lpf: LpfConfig | None = None  # Low-pass filter config (immutable after creation)
    filter_gain: Parameter | None = None  # 0.0 = unfiltered, 1.0 = filtered (only when lpf present)


@dataclass
class CompoundCommand:
    """Command containing multiple sub-commands to execute together."""

    commands: list["Command"]


Command = StopCommand | PatchCommand | CompoundCommand


def parse_source(source_dict: dict) -> SourceConfig:
    """Parse source configuration from JSON."""
    kind = source_dict.get("kind")
    if kind not in ("encoded_bytes", "waveform"):
        raise ValueError(f"Unknown source kind: {kind}")

    return SourceConfig(
        kind=kind,
        name=source_dict.get("name"),
        waveform=source_dict.get("waveform"),
        frequency=source_dict.get("frequency"),
        non_looping_duration=source_dict.get("non_looping_duration"),
        fade_out=source_dict.get("fade_out"),
    )


def parse_lpf(lpf_dict: dict | None) -> LpfConfig | None:
    """Parse low-pass filter configuration from JSON."""
    if lpf_dict is None:
        return None

    return LpfConfig(
        cutoff=float(lpf_dict.get("cutoff", 1000.0)),
        enabled=bool(lpf_dict.get("enabled", True)),
    )


def parse_command(json_data: str | dict) -> Command:
    """
    Parse a JSON command into a Command object.

    Args:
        json_data: JSON string or already-parsed dict

    Returns:
        StopCommand, PatchCommand, or CompoundCommand
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    command_type = data.get("command")

    if command_type == "stop":
        return StopCommand(id=data["id"])

    if command_type == "patch":
        lpf = parse_lpf(data.get("lpf"))
        # Strip lpf if not enabled (it's immutable, so no point creating infrastructure)
        if lpf is not None and not lpf.enabled:
            lpf = None
        # filter_gain only meaningful when lpf is present and enabled
        filter_gain = None
        if lpf is not None:
            filter_gain = parse_param(data.get("filter_gain", 1.0))

        return PatchCommand(
            id=data["id"],
            source=parse_source(data["source"]),
            volume_params=VolumeParams.from_dict(data),
            looping=data.get("looping", False),
            playback_rate=parse_param(data.get("playback_rate", 1.0)),
            start_time=float(data.get("start_time", 0.0)),
            lpf=lpf,
            filter_gain=filter_gain,
        )

    if command_type == "compound":
        sub_commands = [parse_command(cmd) for cmd in data.get("commands", [])]
        return CompoundCommand(commands=sub_commands)

    raise ValueError(f"Unknown command type: {command_type}")


def validate_command(cmd: Command) -> list[str]:
    """
    Validate a parsed command, returning a list of errors.

    Returns empty list if valid.
    """
    errors = []

    if isinstance(cmd, PatchCommand):
        if not cmd.id:
            errors.append("Patch command missing id")

        if cmd.start_time < 0:
            errors.append("start_time cannot be negative")

        src = cmd.source
        if src.kind == "encoded_bytes":
            if not src.name:
                errors.append("encoded_bytes source missing name")

        elif src.kind == "waveform":
            if not src.waveform:
                errors.append("waveform source missing waveform type")
            if src.frequency is None:
                errors.append("waveform source missing frequency")
            if src.waveform and src.waveform not in ("sine", "square", "triangle", "saw"):
                errors.append(f"Unknown waveform type: {src.waveform}")
            if src.fade_out is not None:
                if src.fade_out < 0:
                    errors.append("fade_out cannot be negative")
                if src.non_looping_duration is not None and src.fade_out > src.non_looping_duration:
                    errors.append("fade_out exceeds duration")

        # Validate lpf config
        if cmd.lpf is not None:
            if cmd.lpf.cutoff <= 0:
                errors.append("lpf cutoff must be positive")
            if cmd.lpf.cutoff > 20000:
                errors.append("lpf cutoff exceeds audible range (20kHz)")

    elif isinstance(cmd, StopCommand):
        if not cmd.id:
            errors.append("Stop command missing id")

    elif isinstance(cmd, CompoundCommand):
        if not cmd.commands:
            errors.append("Compound command has no sub-commands")
        for i, sub_cmd in enumerate(cmd.commands):
            sub_errors = validate_command(sub_cmd)
            for err in sub_errors:
                errors.append(f"sub-command {i}: {err}")

    return errors
