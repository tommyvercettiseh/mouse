from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .metrics import derive_trial


@dataclass(slots=True)
class Point:
    t_ms: float
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"t_ms": self.t_ms, "x": self.x, "y": self.y}


@dataclass(slots=True)
class Trial:
    target: dict[str, Any]
    start: dict[str, float]
    points: list[Point]
    click: dict[str, float]
    miss_clicks: list[dict[str, float]] = field(default_factory=list)
    derived: dict[str, Any] = field(default_factory=dict)
    capture_mode: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 7,
            "target": self.target,
            "start": self.start,
            "points": [point.to_dict() for point in self.points],
            "click": self.click,
            "miss_clicks": self.miss_clicks,
            "derived": self.derived,
            "capture_mode": self.capture_mode,
        }


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _xy(value: Any, *, radius: float | None = None, index: int | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {"x": _number(value.get("x")), "y": _number(value.get("y"))}
        if radius is not None or "radius" in value:
            result["radius"] = int(_number(value.get("radius"), radius or 0.0))
        if index is not None or "index" in value:
            result["index"] = int(_number(value.get("index"), index or 0))
        return result
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        result = {"x": _number(value[0]), "y": _number(value[1])}
        if radius is not None:
            result["radius"] = int(radius)
        if index is not None:
            result["index"] = int(index)
        return result
    result = {"x": 0.0, "y": 0.0}
    if radius is not None:
        result["radius"] = int(radius)
    if index is not None:
        result["index"] = int(index)
    return result


def _point(value: Any, fallback_t: float) -> Point | None:
    if isinstance(value, dict):
        return Point(_number(value.get("t_ms"), fallback_t), _number(value.get("x")), _number(value.get("y")))
    if isinstance(value, (list, tuple)):
        if len(value) >= 3:
            return Point(_number(value[0], fallback_t), _number(value[1]), _number(value[2]))
        if len(value) >= 2:
            return Point(fallback_t, _number(value[0]), _number(value[1]))
    return None


def _click(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        down = _number(value.get("down_t_ms"))
        return {
            "down_t_ms": down,
            "up_t_ms": _number(value.get("up_t_ms"), down),
            "x": _number(value.get("x")),
            "y": _number(value.get("y")),
        }
    if isinstance(value, (list, tuple)):
        padded = list(value) + [0.0, 0.0, 0.0, 0.0]
        return {
            "down_t_ms": _number(padded[0]),
            "up_t_ms": _number(padded[1], _number(padded[0])),
            "x": _number(padded[2]),
            "y": _number(padded[3]),
        }
    return {"down_t_ms": 0.0, "up_t_ms": 0.0, "x": 0.0, "y": 0.0}


def normalize_trial(value: Any, index: int = 0) -> Trial | None:
    if not isinstance(value, dict):
        return None

    raw_target = value.get("target", {})
    radius = 26.0
    if isinstance(raw_target, dict):
        radius = _number(raw_target.get("radius"), 26.0)
    elif isinstance(raw_target, (list, tuple)) and len(raw_target) >= 3:
        radius = _number(raw_target[2], 26.0)

    target = _xy(raw_target, radius=radius, index=index)
    start = _xy(value.get("start", {}))
    raw_points = value.get("points", [])
    points = [
        point
        for point_index, raw in enumerate(raw_points if isinstance(raw_points, list) else [])
        if (point := _point(raw, float(point_index * 8))) is not None
    ]
    points.sort(key=lambda point: point.t_ms)
    click = _click(value.get("click", {}))
    raw_misses = value.get("miss_clicks", [])
    misses = [_click(item) for item in raw_misses] if isinstance(raw_misses, list) else []

    derived = value.get("derived", {})
    if not isinstance(derived, dict):
        derived = {}
    if not derived and len(points) >= 2:
        try:
            derived = derive_trial(target, start, [point.to_dict() for point in points], click)
        except (TypeError, ValueError, KeyError):
            derived = {}

    return Trial(
        target=target,
        start={"x": _number(start.get("x")), "y": _number(start.get("y"))},
        points=points,
        click=click,
        miss_clicks=misses,
        derived=derived,
        capture_mode=str(value.get("capture_mode", "normal")),
    )


def normalize_trials(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("trials", [])
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        trial = normalize_trial(raw, index)
        if trial is not None:
            result.append(trial.to_dict())
    return result


def trial_duration_ms(trial: dict[str, Any]) -> float:
    normalized = normalize_trial(trial)
    if normalized is None:
        return 0.0
    values = [point.t_ms for point in normalized.points]
    values.extend((normalized.click["down_t_ms"], normalized.click["up_t_ms"]))
    return max(values, default=0.0)


def visible_points(trial: dict[str, Any], elapsed_ms: float) -> list[dict[str, float]]:
    normalized = normalize_trial(trial)
    if normalized is None or not normalized.points:
        return []
    visible = [point.to_dict() for point in normalized.points if point.t_ms <= elapsed_ms]
    return visible or [normalized.points[0].to_dict()]
