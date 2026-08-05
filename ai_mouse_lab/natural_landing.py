from __future__ import annotations

import math
import random
from typing import Any


MIN_LANDING_RADIUS_PX = 65.0
MAX_LANDING_RADIUS_PX = 105.0
MIN_LANDING_DURATION_MS = 105.0
MAX_LANDING_DURATION_MS = 175.0
MAX_LANDING_SPEED_PX_S = 2400.0
FINAL_LANDING_SPEED_PX_S = 900.0


def _distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    return math.hypot(
        float(second["x"]) - float(first["x"]),
        float(second["y"]) - float(first["y"]),
    )


def _landing_start_index(
    points: list[dict[str, Any]],
    endpoint: dict[str, Any],
    radius: float,
) -> int:
    """Find the beginning of the final contiguous approach to the endpoint."""
    start_index = len(points) - 1
    for index in range(len(points) - 2, -1, -1):
        if _distance(points[index], endpoint) > radius:
            break
        start_index = index
    return start_index


def _speed_cap_near_endpoint(distance_to_endpoint: float, landing_radius: float) -> float:
    progress = max(0.0, min(1.0, distance_to_endpoint / max(1.0, landing_radius)))
    eased = progress * progress * (3.0 - 2.0 * progress)
    return FINAL_LANDING_SPEED_PX_S + (
        MAX_LANDING_SPEED_PX_S - FINAL_LANDING_SPEED_PX_S
    ) * eased


def refine_natural_landing(
    trial: dict[str, Any],
    random_generator: random.Random,
) -> None:
    """Slow only the final approach while preserving its personal route geometry."""
    points = trial.get("points", [])
    click = trial.get("click", {})
    if not isinstance(points, list) or len(points) < 3 or not isinstance(click, dict):
        return

    endpoint = {"x": float(click["x"]), "y": float(click["y"])}
    landing_radius = random_generator.uniform(
        MIN_LANDING_RADIUS_PX,
        MAX_LANDING_RADIUS_PX,
    )
    start_index = _landing_start_index(points, endpoint, landing_radius)
    if start_index >= len(points) - 1:
        return

    start_time = float(points[start_index]["t_ms"])
    end_time = float(points[-1]["t_ms"])
    original_duration = end_time - start_time
    if original_duration <= 0.0:
        return

    adjusted_durations: list[float] = []
    landing_points = points[start_index:]
    for first, second in zip(landing_points, landing_points[1:]):
        elapsed = float(second["t_ms"]) - float(first["t_ms"])
        if elapsed <= 0.0:
            return
        segment_distance = _distance(first, second)
        distance_to_endpoint = _distance(second, endpoint)
        local_speed_cap = _speed_cap_near_endpoint(
            distance_to_endpoint,
            landing_radius,
        )
        adjusted_durations.append(
            max(elapsed, segment_distance / local_speed_cap * 1000.0)
        )

    minimum_duration = random_generator.uniform(
        MIN_LANDING_DURATION_MS,
        MAX_LANDING_DURATION_MS,
    )
    adjusted_total = sum(adjusted_durations)
    duration_factor = max(1.0, minimum_duration / adjusted_total)
    current_time = start_time
    for point, duration in zip(landing_points[1:], adjusted_durations):
        current_time += duration * duration_factor
        point["t_ms"] = round(current_time, 3)

    delay = float(points[-1]["t_ms"]) - end_time
    if delay > 0.0:
        click["down_t_ms"] = round(float(click["down_t_ms"]) + delay, 3)
        click["up_t_ms"] = round(float(click["up_t_ms"]) + delay, 3)

    trial["landing"] = {
        "start_index": start_index,
        "radius_px": round(landing_radius, 3),
        "duration_ms": round(float(points[-1]["t_ms"]) - start_time, 3),
        "speed_cap_px_s": MAX_LANDING_SPEED_PX_S,
        "final_speed_cap_px_s": FINAL_LANDING_SPEED_PX_S,
    }
