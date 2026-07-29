from __future__ import annotations

from bisect import bisect_right
from typing import Any


def trial_duration_ms(trial: dict[str, Any]) -> float:
    points = trial.get("points", [])
    point_end = float(points[-1].get("t_ms", 0.0)) if points else 0.0
    click = trial.get("click", {})
    return max(point_end, float(click.get("up_t_ms", click.get("down_t_ms", 0.0))))


def visible_points(trial: dict[str, Any], elapsed_ms: float, normalized_duration_ms: float | None = None) -> list[dict[str, Any]]:
    points = trial.get("points", [])
    if not points:
        return []
    source_duration = max(1.0, trial_duration_ms(trial))
    source_elapsed = elapsed_ms
    if normalized_duration_ms is not None:
        source_elapsed = elapsed_ms * source_duration / max(1.0, normalized_duration_ms)
    times = [float(point.get("t_ms", 0.0)) for point in points]
    end = bisect_right(times, source_elapsed)
    return points[:max(1, end)]


def scale_point(x: float, y: float, source_width: float, source_height: float, canvas_width: float, canvas_height: float) -> tuple[float, float]:
    margin = 22.0
    usable_width = max(1.0, canvas_width - margin * 2)
    usable_height = max(1.0, canvas_height - margin * 2)
    scale = min(usable_width / max(1.0, source_width), usable_height / max(1.0, source_height))
    offset_x = (canvas_width - source_width * scale) / 2
    offset_y = (canvas_height - source_height * scale) / 2
    return offset_x + x * scale, offset_y + y * scale


def source_size(session: dict[str, Any]) -> tuple[float, float]:
    max_x = 1.0
    max_y = 1.0
    for trial in session.get("trials", []):
        target = trial.get("target", {})
        max_x = max(max_x, float(target.get("x", 0.0)) + float(target.get("radius", 0.0)))
        max_y = max(max_y, float(target.get("y", 0.0)) + float(target.get("radius", 0.0)))
        for point in trial.get("points", []):
            max_x = max(max_x, float(point.get("x", 0.0)))
            max_y = max(max_y, float(point.get("y", 0.0)))
    return max_x + 30.0, max_y + 30.0
