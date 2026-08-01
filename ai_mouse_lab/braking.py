from __future__ import annotations

import math
import statistics
from typing import Any


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _nearest_speed(velocities: list[dict[str, float]], target_distance: float) -> float:
    if not velocities:
        return 0.0
    item = min(velocities, key=lambda value: abs(value["distance_to_target_px"] - target_distance))
    return float(item["speed_px_s"])


def analyze_braking(
    velocities: list[dict[str, float]],
    accelerations: list[dict[str, float]],
    *,
    target_x: float,
    target_y: float,
    radius: float,
    click_down_ms: float,
) -> dict[str, float]:
    """Measure sustained braking and speed near the target.

    Braking begins only after peak speed and requires at least three consecutive
    velocity samples whose speed trend is downward. This avoids treating one noisy
    sample as intentional deceleration.
    """
    if not velocities:
        return {
            "braking_start_ms": 0.0,
            "braking_distance_px": 0.0,
            "braking_duration_ms": 0.0,
            "peak_decel_px_s2": 0.0,
            "target_approach_speed_px_s": 0.0,
            "speed_at_2r_px_s": 0.0,
            "speed_at_1r_px_s": 0.0,
            "speed_at_half_r_px_s": 0.0,
            "final_100ms_speed_px_s": 0.0,
            "slowdown_ratio": 0.0,
        }

    enriched: list[dict[str, float]] = []
    for item in velocities:
        enriched.append(
            {
                **item,
                "distance_to_target_px": math.hypot(item["x"] - target_x, item["y"] - target_y),
            }
        )

    peak_index = max(range(len(enriched)), key=lambda index: enriched[index]["speed_px_s"])
    braking_index = peak_index
    peak_speed = max(enriched[peak_index]["speed_px_s"], 1.0)

    for index in range(peak_index, max(peak_index, len(enriched) - 2)):
        window = enriched[index : index + 4]
        if len(window) < 3:
            break
        speeds = [item["speed_px_s"] for item in window]
        falling_steps = sum(current < previous for previous, current in zip(speeds, speeds[1:]))
        total_drop = speeds[0] - speeds[-1]
        if falling_steps >= 2 and total_drop >= peak_speed * 0.08:
            braking_index = index
            break

    braking = enriched[braking_index]
    braking_start_ms = float(braking["t_ms"])
    braking_distance = float(braking["distance_to_target_px"])
    braking_duration = max(0.0, click_down_ms - braking_start_ms)

    approach_limit = max(radius * 3.0, 45.0)
    approach_speeds = [
        item["speed_px_s"]
        for item in enriched
        if item["distance_to_target_px"] <= approach_limit
    ]
    early_count = max(1, len(enriched) // 3)
    early_speed = _mean([item["speed_px_s"] for item in enriched[:early_count]])
    approach_speed = _mean(approach_speeds)

    final_speeds = [
        item["speed_px_s"]
        for item in enriched
        if click_down_ms - 100.0 <= item["t_ms"] <= click_down_ms
    ]

    peak_deceleration = max(
        (-item["accel_px_s2"] for item in accelerations if item["accel_px_s2"] < 0),
        default=0.0,
    )

    return {
        "braking_start_ms": round(braking_start_ms, 3),
        "braking_distance_px": round(braking_distance, 3),
        "braking_duration_ms": round(braking_duration, 3),
        "peak_decel_px_s2": round(peak_deceleration, 3),
        "target_approach_speed_px_s": round(approach_speed, 3),
        "speed_at_2r_px_s": round(_nearest_speed(enriched, radius * 2.0), 3),
        "speed_at_1r_px_s": round(_nearest_speed(enriched, radius), 3),
        "speed_at_half_r_px_s": round(_nearest_speed(enriched, radius * 0.5), 3),
        "final_100ms_speed_px_s": round(_mean(final_speeds), 3),
        "slowdown_ratio": round(approach_speed / early_speed, 4) if early_speed > 0 else 0.0,
    }
