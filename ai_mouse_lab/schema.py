from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

SCHEMA_VERSION = 7
VIRTUAL_WIDTH = 1920.0
VIRTUAL_HEIGHT = 1080.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_point(value: Any, fallback_t_ms: float = 0.0) -> dict[str, float] | None:
    if isinstance(value, dict):
        return {
            "t_ms": _number(value.get("t_ms"), fallback_t_ms),
            "x": _number(value.get("x")),
            "y": _number(value.get("y")),
        }
    if isinstance(value, (list, tuple)):
        if len(value) >= 3:
            return {"t_ms": _number(value[0], fallback_t_ms), "x": _number(value[1]), "y": _number(value[2])}
        if len(value) >= 2:
            return {"t_ms": fallback_t_ms, "x": _number(value[0]), "y": _number(value[1])}
    return None


def normalize_xy(value: Any, *, radius: float | None = None, index: int | None = None) -> dict[str, float | int]:
    if isinstance(value, dict):
        result: dict[str, float | int] = {"x": _number(value.get("x")), "y": _number(value.get("y"))}
        if radius is not None or "radius" in value:
            result["radius"] = _number(value.get("radius"), radius or 0.0)
        if index is not None or "index" in value:
            result["index"] = int(_number(value.get("index"), float(index or 0)))
        return result
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        result = {"x": _number(value[0]), "y": _number(value[1])}
        if radius is not None:
            result["radius"] = radius
        if index is not None:
            result["index"] = index
        return result
    result = {"x": 0.0, "y": 0.0}
    if radius is not None:
        result["radius"] = radius
    if index is not None:
        result["index"] = index
    return result


def normalize_click(value: Any) -> dict[str, float]:
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
            "up_t_ms": _number(padded[1]),
            "x": _number(padded[2]),
            "y": _number(padded[3]),
        }
    return {"down_t_ms": 0.0, "up_t_ms": 0.0, "x": 0.0, "y": 0.0}


def normalize_trial(value: Any, index: int = 0) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw = deepcopy(value)
    target_raw = raw.get("target", {})
    radius = _number(target_raw.get("radius") if isinstance(target_raw, dict) else None, 26.0)
    points: list[dict[str, float]] = []
    raw_points = raw.get("points", [])
    if isinstance(raw_points, list):
        for point_index, point in enumerate(raw_points):
            normalized = normalize_point(point, point_index * 8.0)
            if normalized is not None:
                points.append(normalized)
    points.sort(key=lambda point: point["t_ms"])
    derived = raw.get("derived")
    if not isinstance(derived, dict):
        derived = {}
    misses_raw = raw.get("miss_clicks", [])
    misses = [normalize_click(item) for item in misses_raw] if isinstance(misses_raw, list) else []
    return {
        **raw,
        "schema_version": SCHEMA_VERSION,
        "capture_mode": str(raw.get("capture_mode", "normal")),
        "coordinate_space": "virtual_1920x1080",
        "target": normalize_xy(target_raw, radius=radius, index=index),
        "start": normalize_xy(raw.get("start", {})),
        "points": points,
        "click": normalize_click(raw.get("click", {})),
        "miss_clicks": misses,
        "derived": derived,
    }


def normalize_trials(values: Iterable[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        trial = normalize_trial(value, index)
        if trial is not None:
            output.append(trial)
    return output


def normalize_session(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        base: dict[str, Any] = {}
        source_trials = value
    elif isinstance(value, dict):
        base = deepcopy(value)
        source_trials = value.get("trials", [])
    else:
        base = {}
        source_trials = []
    trials = normalize_trials(source_trials if isinstance(source_trials, list) else [])
    base.update(
        {
            "schema_version": SCHEMA_VERSION,
            "coordinate_space": "virtual_1920x1080",
            "width": VIRTUAL_WIDTH,
            "height": VIRTUAL_HEIGHT,
            "trials": trials,
            "trial_count": len(trials),
        }
    )
    return base


def validate_trial(trial: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(trial.get("target"), dict):
        errors.append("target must be an object")
    if not isinstance(trial.get("start"), dict):
        errors.append("start must be an object")
    points = trial.get("points")
    if not isinstance(points, list) or len(points) < 2:
        errors.append("at least two points are required")
    elif any(not isinstance(point, dict) for point in points):
        errors.append("every point must be an object")
    if not isinstance(trial.get("click"), dict):
        errors.append("click must be an object")
    if not isinstance(trial.get("derived"), dict):
        errors.append("derived must be an object")
    return errors
