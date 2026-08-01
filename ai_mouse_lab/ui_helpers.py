from __future__ import annotations

import math
from typing import Any

TRACE_COLOR = "#7aa2ff"
TRACE_WIDTH = 2
TRACE_MAX_POINTS = 220


def is_target_hit(x: float, y: float, target: dict[str, Any]) -> bool:
    return math.hypot(
        float(x) - float(target["x"]),
        float(y) - float(target["y"]),
    ) <= float(target["radius"])


def trace_coordinates(
    points: list[dict[str, Any]],
    limit: int = TRACE_MAX_POINTS,
) -> list[float]:
    coordinates: list[float] = []
    for point in points[-limit:]:
        coordinates.extend((float(point["x"]), float(point["y"])))
    return coordinates


def click_is_visible(click: dict[str, Any], elapsed_ms: float) -> bool:
    try:
        return float(click["down_t_ms"]) <= float(elapsed_ms)
    except (KeyError, TypeError, ValueError):
        return False


def visible_miss_clicks(
    trial: dict[str, Any],
    elapsed_ms: float,
) -> list[dict[str, Any]]:
    misses = trial.get("miss_clicks", [])
    if not isinstance(misses, list):
        return []
    return [
        click
        for click in misses
        if isinstance(click, dict) and click_is_visible(click, elapsed_ms)
    ]
