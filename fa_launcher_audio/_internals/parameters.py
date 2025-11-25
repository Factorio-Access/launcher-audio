"""Parameter system for time-based value interpolation."""

from dataclasses import dataclass
from typing import Literal, Protocol


class Parameter(Protocol):
    """Protocol for parameter values (static or time-based)."""

    def get_value(self, time_seconds: float) -> float:
        """Get the parameter value at the given time."""
        ...

    def is_constant(self) -> bool:
        """True if the value never changes."""
        ...


@dataclass
class TimePoint:
    """A value at a specific time for interpolation."""

    time: float  # Time in seconds
    value: float
    interpolation: Literal["linear", "jump"] = "linear"


class StaticParam:
    """A constant parameter value."""

    def __init__(self, value: float):
        self._value = value

    def get_value(self, time_seconds: float) -> float:
        return self._value

    def is_constant(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"StaticParam({self._value})"


class TimeEnvelope:
    """
    A parameter that interpolates between time points.

    Supports linear interpolation and jump (step) interpolation.
    """

    def __init__(self, points: list[TimePoint]):
        if not points:
            raise ValueError("TimeEnvelope requires at least one point")
        self._points = sorted(points, key=lambda p: p.time)

    def get_value(self, time_seconds: float) -> float:
        """Get interpolated value at the given time."""
        if not self._points:
            return 0.0

        # Before first point: return first value
        if time_seconds <= self._points[0].time:
            return self._points[0].value

        # After last point: return last value
        if time_seconds >= self._points[-1].time:
            return self._points[-1].value

        # Find surrounding points
        for i in range(len(self._points) - 1):
            p1 = self._points[i]
            p2 = self._points[i + 1]

            if p1.time <= time_seconds < p2.time:
                # Check interpolation type of the NEXT point
                if p2.interpolation == "jump":
                    # Hold previous value until we reach the next point
                    return p1.value
                else:  # linear
                    # Linear interpolation
                    t = (time_seconds - p1.time) / (p2.time - p1.time)
                    return p1.value + t * (p2.value - p1.value)

        # Fallback (shouldn't reach here)
        return self._points[-1].value

    def is_constant(self) -> bool:
        return len(self._points) <= 1

    def __repr__(self) -> str:
        return f"TimeEnvelope({self._points})"


def parse_param(value: float | int | list[dict]) -> StaticParam | TimeEnvelope:
    """
    Parse a JSON parameter value to a Parameter object.

    Args:
        value: Either a static number or a list of time points:
               [{"time": 0.0, "value": 1.0, "interpolation_from_prev": "linear"}, ...]

    Returns:
        StaticParam or TimeEnvelope
    """
    if isinstance(value, (int, float)):
        return StaticParam(float(value))

    if isinstance(value, list):
        points = []
        for item in value:
            point = TimePoint(
                time=float(item["time"]),
                value=float(item["value"]),
                interpolation=item.get("interpolation_from_prev", "linear"),
            )
            points.append(point)
        return TimeEnvelope(points)

    raise ValueError(f"Invalid parameter value: {value}")


@dataclass
class GainParams:
    """Container for overall, left, and right gain parameters."""

    overall: Parameter
    left: Parameter
    right: Parameter

    @classmethod
    def from_dict(cls, gains_dict: dict) -> "GainParams":
        """Parse gains from JSON dict."""
        return cls(
            overall=parse_param(gains_dict.get("overall", 1.0)),
            left=parse_param(gains_dict.get("left", 1.0)),
            right=parse_param(gains_dict.get("right", 1.0)),
        )

    def get_values(self, time_seconds: float) -> tuple[float, float, float]:
        """Get (overall, left, right) values at the given time."""
        return (
            self.overall.get_value(time_seconds),
            self.left.get_value(time_seconds),
            self.right.get_value(time_seconds),
        )

    def is_constant(self) -> bool:
        """True if all gain parameters are constant."""
        return (
            self.overall.is_constant()
            and self.left.is_constant()
            and self.right.is_constant()
        )
