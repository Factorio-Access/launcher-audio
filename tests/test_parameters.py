"""Tests for the parameter system."""

import pytest
from fa_launcher_audio._internals.parameters import (
    StaticParam,
    TimeEnvelope,
    TimePoint,
    parse_param,
    VolumeParams,
)


class TestStaticParam:
    def test_returns_constant_value(self):
        param = StaticParam(0.5)
        assert param.get_value(0.0) == 0.5
        assert param.get_value(100.0) == 0.5
        assert param.get_value(-5.0) == 0.5

    def test_is_constant(self):
        param = StaticParam(1.0)
        assert param.is_constant() is True


class TestTimeEnvelope:
    def test_single_point_is_constant(self):
        env = TimeEnvelope([TimePoint(0.0, 1.0)])
        assert env.is_constant() is True
        assert env.get_value(0.0) == 1.0
        assert env.get_value(100.0) == 1.0

    def test_before_first_point_returns_first_value(self):
        env = TimeEnvelope([
            TimePoint(1.0, 0.5),
            TimePoint(2.0, 1.0),
        ])
        assert env.get_value(0.0) == 0.5
        assert env.get_value(0.9) == 0.5

    def test_after_last_point_returns_last_value(self):
        env = TimeEnvelope([
            TimePoint(0.0, 0.0),
            TimePoint(1.0, 1.0),
        ])
        assert env.get_value(1.0) == 1.0
        assert env.get_value(100.0) == 1.0

    def test_linear_interpolation(self):
        env = TimeEnvelope([
            TimePoint(0.0, 0.0, "linear"),
            TimePoint(1.0, 1.0, "linear"),
        ])
        assert env.get_value(0.0) == pytest.approx(0.0)
        assert env.get_value(0.25) == pytest.approx(0.25)
        assert env.get_value(0.5) == pytest.approx(0.5)
        assert env.get_value(0.75) == pytest.approx(0.75)
        assert env.get_value(1.0) == pytest.approx(1.0)

    def test_jump_interpolation(self):
        env = TimeEnvelope([
            TimePoint(0.0, 0.0, "linear"),
            TimePoint(1.0, 1.0, "jump"),
        ])
        # Jump means hold previous value until we reach the point
        assert env.get_value(0.0) == 0.0
        assert env.get_value(0.5) == 0.0
        assert env.get_value(0.99) == 0.0
        assert env.get_value(1.0) == 1.0  # Jumps at exact time

    def test_multiple_segments(self):
        env = TimeEnvelope([
            TimePoint(0.0, 0.0, "linear"),
            TimePoint(1.0, 1.0, "linear"),
            TimePoint(2.0, 0.5, "linear"),
        ])
        assert env.get_value(0.5) == pytest.approx(0.5)
        assert env.get_value(1.0) == pytest.approx(1.0)
        assert env.get_value(1.5) == pytest.approx(0.75)
        assert env.get_value(2.0) == pytest.approx(0.5)

    def test_points_sorted_automatically(self):
        # Points given out of order
        env = TimeEnvelope([
            TimePoint(2.0, 1.0),
            TimePoint(0.0, 0.0),
            TimePoint(1.0, 0.5),
        ])
        assert env.get_value(0.0) == 0.0
        assert env.get_value(1.0) == 0.5
        assert env.get_value(2.0) == 1.0

    def test_empty_raises_error(self):
        with pytest.raises(ValueError):
            TimeEnvelope([])


class TestParseParam:
    def test_parse_static_int(self):
        param = parse_param(1)
        assert isinstance(param, StaticParam)
        assert param.get_value(0) == 1.0

    def test_parse_static_float(self):
        param = parse_param(0.75)
        assert isinstance(param, StaticParam)
        assert param.get_value(0) == 0.75

    def test_parse_envelope(self):
        param = parse_param([
            {"time": 0.0, "value": 0.0},
            {"time": 1.0, "value": 1.0, "interpolation_from_prev": "linear"},
        ])
        assert isinstance(param, TimeEnvelope)
        assert param.get_value(0.5) == pytest.approx(0.5)

    def test_parse_envelope_with_jump(self):
        param = parse_param([
            {"time": 0.0, "value": 0.0},
            {"time": 1.0, "value": 1.0, "interpolation_from_prev": "jump"},
        ])
        assert isinstance(param, TimeEnvelope)
        assert param.get_value(0.5) == 0.0  # Jump holds previous


class TestVolumeParams:
    def test_from_dict_defaults(self):
        params = VolumeParams.from_dict({})
        assert params.volume.get_value(0) == 1.0
        assert params.pan.get_value(0) == 0.0

    def test_from_dict_static(self):
        params = VolumeParams.from_dict({
            "volume": 0.5,
            "pan": -0.5,
        })
        assert params.volume.get_value(0) == 0.5
        assert params.pan.get_value(0) == -0.5

    def test_get_values(self):
        params = VolumeParams.from_dict({
            "volume": 0.5,
            "pan": 0.75,
        })
        volume, pan = params.get_values(0)
        assert volume == 0.5
        assert pan == 0.75

    def test_is_constant_true(self):
        params = VolumeParams.from_dict({"volume": 0.5, "pan": 0.0})
        assert params.is_constant() is True

    def test_is_constant_false(self):
        params = VolumeParams.from_dict({
            "volume": [{"time": 0, "value": 0}, {"time": 1, "value": 1}],
            "pan": 0.0,
        })
        assert params.is_constant() is False
