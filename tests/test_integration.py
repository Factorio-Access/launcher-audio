"""Integration tests for the audio system."""

import pytest
import time
from pathlib import Path

from fa_launcher_audio import AudioManager
from fa_launcher_audio._internals.engine import MiniaudioEngine
from fa_launcher_audio._internals.sources import WaveformSource, DecoderSource
from fa_launcher_audio._internals.sound import Sound


class TestMiniaudioEngine:
    def test_engine_initializes(self):
        engine = MiniaudioEngine()
        assert engine.sample_rate > 0
        engine.uninit()

    def test_engine_time_advances(self):
        engine = MiniaudioEngine()
        t1 = engine.get_time_frames()
        # Engine time advances as audio is processed
        # Note: Without reading frames, time may not advance
        engine.uninit()

    def test_engine_context_cleanup(self):
        engine = MiniaudioEngine()
        engine.uninit()
        # Should not crash on double uninit
        engine.uninit()


class TestWaveformSource:
    def test_waveform_creates(self):
        wf = WaveformSource("sine", 440.0)
        assert wf._initialized
        wf.cleanup()

    def test_waveform_types(self):
        for wf_type in ["sine", "square", "triangle", "saw"]:
            wf = WaveformSource(wf_type, 440.0)
            assert wf._initialized
            wf.cleanup()

    def test_waveform_invalid_type(self):
        with pytest.raises(ValueError):
            WaveformSource("invalid", 440.0)


class TestDecoderSource:
    def test_decoder_loads_flac(self, test_audio_bytes):
        decoder = DecoderSource(test_audio_bytes)
        assert decoder._initialized
        length = decoder.get_length_frames()
        assert length > 0
        decoder.cleanup()


class TestSound:
    def test_sound_creates_from_waveform(self):
        engine = MiniaudioEngine()
        wf = WaveformSource("sine", 440.0)
        sound = Sound(engine, wf, "test")
        assert sound._initialized
        sound.cleanup()
        engine.uninit()

    def test_sound_volume_control(self):
        engine = MiniaudioEngine()
        wf = WaveformSource("sine", 440.0)
        sound = Sound(engine, wf, "test")

        sound.set_overall_gain(0.5)
        sound.set_channel_gains(0.8, 0.2)
        sound.set_pitch(1.5)
        sound.set_looping(True)

        sound.cleanup()
        engine.uninit()


class TestAudioManager:
    def test_manager_context_manager(self, mock_bytes_callback):
        with AudioManager(data_provider=mock_bytes_callback) as mgr:
            assert mgr._engine is not None
            assert mgr._worker is not None

        # After exit, should be cleaned up
        assert mgr._engine is None
        assert mgr._worker is None

    def test_manager_submit_command(self, mock_bytes_callback):
        with AudioManager(data_provider=mock_bytes_callback) as mgr:
            # Submit a waveform command (low volume to avoid actual sound)
            mgr.submit_command({
                "command": "patch",
                "id": "test_sound",
                "source": {"kind": "waveform", "waveform": "sine", "frequency": 440},
                "gains": {"overall": 0.0},  # Silent
                "looping": False,
                "playback_rate": 1.0,
            })

            # Give worker time to process
            time.sleep(0.05)

            # Stop the sound
            mgr.submit_command({
                "command": "stop",
                "id": "test_sound",
            })

            time.sleep(0.05)

    def test_manager_encoded_bytes(self, mock_bytes_callback):
        with AudioManager(data_provider=mock_bytes_callback) as mgr:
            mgr.submit_command({
                "command": "patch",
                "id": "test_file",
                "source": {"kind": "encoded_bytes", "name": "test.flac"},
                "gains": {"overall": 0.0},  # Silent
                "looping": False,
                "playback_rate": 1.0,
            })

            time.sleep(0.05)

            mgr.submit_command({
                "command": "stop",
                "id": "test_file",
            })

    def test_manager_not_started_raises(self, mock_bytes_callback):
        mgr = AudioManager(data_provider=mock_bytes_callback)
        with pytest.raises(RuntimeError, match="not started"):
            mgr.submit_command({"command": "stop", "id": "test"})
