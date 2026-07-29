from __future__ import annotations

import math
from typing import Any

TRACE_COLOR = "#7aa2ff"
TRACE_WIDTH = 2
TRACE_MAX_POINTS = 220


def is_target_hit(x: float, y: float, target: dict[str, Any]) -> bool:
    return math.hypot(float(x) - float(target["x"]), float(y) - float(target["y"])) <= float(target["radius"])


def trace_coordinates(points: list[dict[str, Any]], limit: int = TRACE_MAX_POINTS) -> list[float]:
    coordinates: list[float] = []
    for point in points[-limit:]:
        coordinates.extend((float(point["x"]), float(point["y"])))
    return coordinates
