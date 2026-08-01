from __future__ import annotations

import math
import statistics
from typing import Any


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * p
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {key: 0.0 for key in ("mean", "median", "stdev", "p10", "p90", "min", "max")}
    return {
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "p10": round(percentile(values, 0.10), 3),
        "p90": round(percentile(values, 0.90), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def smooth_points(points: list[dict[str, Any]], window: int = 5) -> list[dict[str, float]]:
    source = [
        {"t_ms": float(point["t_ms"]), "x": float(point["x"]), "y": float(point["y"])}
        for point in points
    ]
    if window < 2 or len(source) <= 2:
        return source
    radius = window // 2
    output: list[dict[str, float]] = []
    for index, point in enumerate(source):
        lower = max(0, index - radius)
        upper = min(len(source), index + radius + 1)
        chunk = source[lower:upper]
        output.append({
            "t_ms": point["t_ms"],
            "x": sum(item["x"] for item in chunk) / len(chunk),
            "y": sum(item["y"] for item in chunk) / len(chunk),
        })
    return output


def _densify(points: list[dict[str, Any]], max_step_px: float) -> list[dict[str, float]]:
    source = [
        {"t_ms": float(point["t_ms"]), "x": float(point["x"]), "y": float(point["y"])}
        for point in points
    ]
    if len(source) < 2:
        return source
    dense = [source[0]]
    for first, second in zip(source, source[1:]):
        distance = math.hypot(second["x"] - first["x"], second["y"] - first["y"])
        steps = max(1, int(math.ceil(distance / max(max_step_px, 1.0))))
        for step in range(1, steps + 1):
            fraction = step / steps
            dense.append({
                "t_ms": first["t_ms"] + (second["t_ms"] - first["t_ms"]) * fraction,
                "x": first["x"] + (second["x"] - first["x"]) * fraction,
                "y": first["y"] + (second["y"] - first["y"]) * fraction,
            })
    return dense


def _kinematics(points: list[dict[str, float]]) -> tuple[list[dict[str, float]], list[dict[str, float]], list[dict[str, float]], float]:
    velocities: list[dict[str, float]] = []
    accelerations: list[dict[str, float]] = []
    jerks: list[dict[str, float]] = []
    path_length = 0.0

    for first, second in zip(points, points[1:]):
        dt_s = max(0.001, (second["t_ms"] - first["t_ms"]) / 1000.0)
        dx = second["x"] - first["x"]
        dy = second["y"] - first["y"]
        distance = math.hypot(dx, dy)
        path_length += distance
        velocities.append({
            "t_ms": second["t_ms"],
            "speed_px_s": distance / dt_s,
            "vx_px_s": dx / dt_s,
            "vy_px_s": dy / dt_s,
            "x": second["x"],
            "y": second["y"],
        })

    for first, second in zip(velocities, velocities[1:]):
        dt_s = max(0.001, (second["t_ms"] - first["t_ms"]) / 1000.0)
        accelerations.append({
            "t_ms": second["t_ms"],
            "accel_px_s2": (second["speed_px_s"] - first["speed_px_s"]) / dt_s,
        })

    for first, second in zip(accelerations, accelerations[1:]):
        dt_s = max(0.001, (second["t_ms"] - first["t_ms"]) / 1000.0)
        jerks.append({
            "t_ms": second["t_ms"],
            "jerk_px_s3": (second["accel_px_s2"] - first["accel_px_s2"]) / dt_s,
        })

    return velocities, accelerations, jerks, path_length


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def derive_trial(
    target: dict[str, float],
    start: dict[str, float],
    points: list[dict[str, Any]],
    click: dict[str, Any],
) -> dict[str, Any]:
    if len(points) < 2:
        raise ValueError("At least two route points are required")

    clean = smooth_points(points)
    target_x = float(target["x"])
    target_y = float(target["y"])
    radius = float(target["radius"])
    start_x = float(start["x"])
    start_y = float(start["y"])

    direction_x = target_x - start_x
    direction_y = target_y - start_y
    straight_distance = math.hypot(direction_x, direction_y)
    unit_x, unit_y = (
        (direction_x / straight_distance, direction_y / straight_distance)
        if straight_distance > 0
        else (0.0, 0.0)
    )

    velocities, accelerations, jerks, path_length = _kinematics(clean)

    reaction_ms = 0.0
    for point in clean:
        if math.hypot(point["x"] - start_x, point["y"] - start_y) >= 3.0:
            reaction_ms = point["t_ms"]
            break

    motion = _densify(points, max(2.0, radius / 4.0))
    inside = [math.hypot(point["x"] - target_x, point["y"] - target_y) <= radius for point in motion]
    click_x = float(click.get("x", motion[-1]["x"]))
    click_y = float(click.get("y", motion[-1]["y"]))
    if math.hypot(click_x - target_x, click_y - target_y) <= radius and not inside[-1]:
        inside[-1] = True

    first_entry_index = next((index for index, value in enumerate(inside) if value), None)
    first_entry_ms = motion[first_entry_index]["t_ms"] if first_entry_index is not None else None
    entry_count = sum(1 for previous, current in zip(inside, inside[1:]) if not previous and current)
    exit_count = sum(1 for previous, current in zip(inside, inside[1:]) if previous and not current)

    radial_overshoot = 0.0
    if first_entry_index is not None:
        radial_overshoot = max(
            max(0.0, math.hypot(point["x"] - target_x, point["y"] - target_y) - radius)
            for point in motion[first_entry_index:]
        )

    directional_overshoot = 0.0
    if straight_distance > 0 and motion:
        projections = [
            (point["x"] - start_x) * unit_x + (point["y"] - start_y) * unit_y
            for point in motion
        ]
        peak_index = max(range(len(projections)), key=projections.__getitem__)
        peak_projection = projections[peak_index]
        far_edge = straight_distance + radius
        later_minimum = min(projections[peak_index:])
        reversal = peak_projection - later_minimum
        if peak_projection > far_edge and reversal >= max(2.0, radius * 0.12):
            directional_overshoot = peak_projection - far_edge

    overshoot = max(radial_overshoot, directional_overshoot)
    correction_count = max(0, entry_count - 1)
    if directional_overshoot > 0:
        correction_count = max(1, correction_count)

    click_down_ms = float(click.get("down_t_ms") or clean[-1]["t_ms"])
    click_up_ms = float(click.get("up_t_ms") or click_down_ms)

    peak_speed_index = max(range(len(velocities)), key=lambda index: velocities[index]["speed_px_s"]) if velocities else 0
    peak_speed = velocities[peak_speed_index]["speed_px_s"] if velocities else 0.0
    peak_speed_time_ms = velocities[peak_speed_index]["t_ms"] if velocities else 0.0

    braking_start_index = peak_speed_index
    if velocities:
        threshold = peak_speed * 0.92
        for index in range(peak_speed_index, len(velocities)):
            following = velocities[index:min(len(velocities), index + 3)]
            if following and all(item["speed_px_s"] <= threshold for item in following):
                braking_start_index = index
                break
    braking_start_ms = velocities[braking_start_index]["t_ms"] if velocities else 0.0
    braking_x = velocities[braking_start_index]["x"] if velocities else start_x
    braking_y = velocities[braking_start_index]["y"] if velocities else start_y
    braking_distance_px = math.hypot(target_x - braking_x, target_y - braking_y)
    braking_duration_ms = max(0.0, click_down_ms - braking_start_ms)

    approach_start_distance = max(radius * 3.0, 45.0)
    approach_speeds = [
        item["speed_px_s"]
        for item in velocities
        if math.hypot(item["x"] - target_x, item["y"] - target_y) <= approach_start_distance
    ]
    target_approach_speed = _mean(approach_speeds)

    speed_at_entry = 0.0
    if first_entry_ms is not None and velocities:
        speed_at_entry = min(velocities, key=lambda item: abs(item["t_ms"] - first_entry_ms))["speed_px_s"]

    early_speed_values = [item["speed_px_s"] for item in velocities[:max(1, len(velocities) // 3)]]
    early_speed = _mean(early_speed_values)
    slowdown_ratio = target_approach_speed / early_speed if early_speed > 0 else 0.0

    peak_acceleration = max((abs(item["accel_px_s2"]) for item in accelerations), default=0.0)
    peak_deceleration = max((-item["accel_px_s2"] for item in accelerations if item["accel_px_s2"] < 0), default=0.0)
    peak_jerk = max((abs(item["jerk_px_s3"]) for item in jerks), default=0.0)

    return {
        "reaction_ms": round(reaction_ms, 3),
        "movement_time_ms": round(click_down_ms, 3),
        "first_entry_ms": round(first_entry_ms, 3) if first_entry_ms is not None else None,
        "click_delay_ms": round(max(0.0, click_down_ms - (first_entry_ms or click_down_ms)), 3),
        "hold_ms": round(max(0.0, click_up_ms - click_down_ms), 3),
        "distance_px": round(straight_distance, 3),
        "path_length_px": round(path_length, 3),
        "path_efficiency": round(straight_distance / path_length, 4) if path_length > 0 else 0.0,
        "click_error_px": round(math.hypot(click_x - target_x, click_y - target_y), 3),
        "peak_speed_px_s": round(peak_speed, 3),
        "peak_speed_time_ms": round(peak_speed_time_ms, 3),
        "peak_accel_px_s2": round(peak_acceleration, 3),
        "peak_decel_px_s2": round(peak_deceleration, 3),
        "peak_jerk_px_s3": round(peak_jerk, 3),
        "braking_start_ms": round(braking_start_ms, 3),
        "braking_distance_px": round(braking_distance_px, 3),
        "braking_duration_ms": round(braking_duration_ms, 3),
        "target_approach_speed_px_s": round(target_approach_speed, 3),
        "speed_at_entry_px_s": round(speed_at_entry, 3),
        "slowdown_ratio": round(slowdown_ratio, 4),
        "overshoot_px": round(overshoot, 3),
        "radial_overshoot_px": round(radial_overshoot, 3),
        "directional_overshoot_px": round(directional_overshoot, 3),
        "correction_count": correction_count,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "miss": first_entry_index is None,
    }
