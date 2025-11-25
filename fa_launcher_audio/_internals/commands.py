"""JSON command parsing for the audio system."""

import json
from dataclasses import dataclass
from typing import Literal, Callable

from fa_launcher_audio._internals.parameters import (
    GainParams,
    Parameter,
    parse_param,
)


@dataclass
class StopCommand:
    """Command to stop a sound."""

    id: str


@dataclass
class SourceConfig:
    """Configuration for a sound source."""

    kind: Literal["encoded_bytes", "waveform", "timeline"]
    # For encoded_bytes:
    name: str | None = None
    # For waveform:
    waveform: str | None = None  # sine, square, triangle, saw
    frequency: float | None = None
    non_looping_duration: float | None = None
    # For timeline:
    entries: list[dict] | None = None


@dataclass
class PatchCommand:
    """Command to create or update a sound."""

    id: str
    source: SourceConfig
    gains: GainParams
    looping: bool
    playback_rate: Parameter


Command = StopCommand | PatchCommand


def parse_source(source_dict: dict) -> SourceConfig:
    """Parse source configuration from JSON."""
    kind = source_dict.get("kind")
    if kind not in ("encoded_bytes", "waveform", "timeline"):
        raise ValueError(f"Unknown source kind: {kind}")

    return SourceConfig(
        kind=kind,
        name=source_dict.get("name"),
        waveform=source_dict.get("waveform"),
        frequency=source_dict.get("frequency"),
        non_looping_duration=source_dict.get("non_looping_duration"),
        entries=source_dict.get("entries"),
    )


def parse_command(json_data: str | dict) -> Command:
    """
    Parse a JSON command into a Command object.

    Args:
        json_data: JSON string or already-parsed dict

    Returns:
        StopCommand or PatchCommand
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    command_type = data.get("command")

    if command_type == "stop":
        return StopCommand(id=data["id"])

    if command_type == "patch":
        return PatchCommand(
            id=data["id"],
            source=parse_source(data["source"]),
            gains=GainParams.from_dict(data.get("gains", {})),
            looping=data.get("looping", False),
            playback_rate=parse_param(data.get("playback_rate", 1.0)),
        )

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

        elif src.kind == "timeline":
            if src.entries is None:
                errors.append("timeline source missing entries")

    elif isinstance(cmd, StopCommand):
        if not cmd.id:
            errors.append("Stop command missing id")

    return errors
