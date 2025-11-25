"""Tests for command parsing."""

import pytest
from fa_launcher_audio._internals.commands import (
    parse_command,
    validate_command,
    PatchCommand,
    StopCommand,
)


class TestParseCommand:
    def test_parse_stop_command(self):
        cmd = parse_command({
            "command": "stop",
            "id": "sound_123",
        })
        assert isinstance(cmd, StopCommand)
        assert cmd.id == "sound_123"

    def test_parse_stop_command_from_json(self):
        cmd = parse_command('{"command": "stop", "id": "test"}')
        assert isinstance(cmd, StopCommand)
        assert cmd.id == "test"

    def test_parse_patch_waveform(self):
        cmd = parse_command({
            "command": "patch",
            "id": "beep",
            "source": {
                "kind": "waveform",
                "waveform": "sine",
                "frequency": 440,
            },
            "gains": {"overall": 0.5},
            "looping": True,
            "playback_rate": 1.0,
        })
        assert isinstance(cmd, PatchCommand)
        assert cmd.id == "beep"
        assert cmd.source.kind == "waveform"
        assert cmd.source.waveform == "sine"
        assert cmd.source.frequency == 440
        assert cmd.looping is True

    def test_parse_patch_encoded_bytes(self):
        cmd = parse_command({
            "command": "patch",
            "id": "music",
            "source": {
                "kind": "encoded_bytes",
                "name": "song.mp3",
            },
            "gains": {"overall": 1.0, "left": 1.0, "right": 0.5},
            "looping": False,
            "playback_rate": 1.5,
        })
        assert isinstance(cmd, PatchCommand)
        assert cmd.source.kind == "encoded_bytes"
        assert cmd.source.name == "song.mp3"
        assert cmd.gains.right.get_value(0) == 0.5
        assert cmd.playback_rate.get_value(0) == 1.5

    def test_parse_patch_with_time_envelope(self):
        cmd = parse_command({
            "command": "patch",
            "id": "fading",
            "source": {"kind": "waveform", "waveform": "sine", "frequency": 440},
            "gains": {
                "overall": [
                    {"time": 0.0, "value": 0.0},
                    {"time": 1.0, "value": 1.0, "interpolation_from_prev": "linear"},
                ],
            },
            "looping": False,
            "playback_rate": 1.0,
        })
        assert cmd.gains.overall.get_value(0.5) == pytest.approx(0.5)

    def test_parse_patch_default_gains(self):
        cmd = parse_command({
            "command": "patch",
            "id": "test",
            "source": {"kind": "waveform", "waveform": "sine", "frequency": 440},
        })
        # Should default to 1.0 for all gains
        assert cmd.gains.overall.get_value(0) == 1.0
        assert cmd.gains.left.get_value(0) == 1.0
        assert cmd.gains.right.get_value(0) == 1.0

    def test_parse_unknown_command_raises(self):
        with pytest.raises(ValueError, match="Unknown command type"):
            parse_command({"command": "unknown"})


class TestValidateCommand:
    def test_valid_stop_command(self):
        cmd = StopCommand(id="test")
        errors = validate_command(cmd)
        assert errors == []

    def test_stop_missing_id(self):
        cmd = StopCommand(id="")
        errors = validate_command(cmd)
        assert "missing id" in errors[0].lower()

    def test_valid_waveform_patch(self):
        cmd = parse_command({
            "command": "patch",
            "id": "test",
            "source": {"kind": "waveform", "waveform": "sine", "frequency": 440},
        })
        errors = validate_command(cmd)
        assert errors == []

    def test_waveform_missing_type(self):
        cmd = parse_command({
            "command": "patch",
            "id": "test",
            "source": {"kind": "waveform", "frequency": 440},
        })
        errors = validate_command(cmd)
        assert any("waveform type" in e.lower() for e in errors)

    def test_waveform_missing_frequency(self):
        cmd = parse_command({
            "command": "patch",
            "id": "test",
            "source": {"kind": "waveform", "waveform": "sine"},
        })
        errors = validate_command(cmd)
        assert any("frequency" in e.lower() for e in errors)

    def test_encoded_bytes_missing_name(self):
        cmd = parse_command({
            "command": "patch",
            "id": "test",
            "source": {"kind": "encoded_bytes"},
        })
        errors = validate_command(cmd)
        assert any("name" in e.lower() for e in errors)
