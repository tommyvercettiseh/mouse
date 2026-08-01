from __future__ import annotations

import math
import statistics


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _nearest_speed(velocities: list[dict[str, float]], target_distance: float) -> float:
    if not velocities:
        return 0.0
    item = min(
        velocities,
        key=lambda value: abs(value["distance_to_target_px"] - target_distance),
    )
    return float(item["speed_px_s"])


def _empty_approach() -> dict[str, float]:
    return {
        "approach_correction_count": 0.0,
        "approach_deviation_px": 0.0,
        "approach_correction_ms": 0.0,
        "approach_angle_change_deg": 0.0,
    }


def _analyze_approach_corrections(
    velocities: list[dict[str, float]],
    *,
    target_x: float,
    target_y: float,
    radius: float,
) -> dict[str, float]:
    """Count meaningful steering reversals before the first target entry.

    This deliberately excludes movement inside or beyond the target. Those events
    remain part of entry/exit and overshoot metrics instead of being mislabeled as
    an approach correction.
    """
    if len(velocities) < 4:
        return _empty_approach()

    start_x = float(velocities[0]["x"])
    start_y = float(velocities[0]["y"])
    direction_x = target_x - start_x
    direction_y = target_y - start_y
    distance = math.hypot(direction_x, direction_y)
    if distance < 1.0:
        return _empty_approach()

    unit_x, unit_y = direction_x / distance, direction_y / distance
    side_x, side_y = -unit_y, unit_x
    samples: list[dict[str, float]] = []
    for item in velocities:
        x = float(item["x"])
        y = float(item["y"])
        if math.hypot(x - target_x, y - target_y) <= radius:
            break
        along = (x - start_x) * unit_x + (y - start_y) * unit_y
        if along > distance + radius:
            break
        samples.append(
            {
                "t_ms": float(item["t_ms"]),
                "along": along,
                "side": (x - start_x) * side_x + (y - start_y) * side_y,
            }
        )

    if len(samples) < 4:
        return _empty_approach()

    threshold = max(3.0, radius * 0.12)
    max_deviation = max(abs(item["side"]) for item in samples)
    correction_count = 0
    first_correction_ms = 0.0
    max_angle_change = 0.0
    last_turn_index = -10

    for index in range(1, len(samples) - 1):
        before, current, after = samples[index - 1], samples[index], samples[index + 1]
        side_before = current["side"] - before["side"]
        side_after = after["side"] - current["side"]
        if side_before == 0.0 or side_after == 0.0:
            continue
        if side_before * side_after >= 0.0:
            continue
        if abs(current["side"]) < threshold:
            continue
        if index - last_turn_index < 2:
            continue

        correction_count += 1
        last_turn_index = index
        if first_correction_ms == 0.0:
            first_correction_ms = current["t_ms"]

        first_x = current["along"] - before["along"]
        first_y = current["side"] - before["side"]
        second_x = after["along"] - current["along"]
        second_y = after["side"] - current["side"]
        first_length = math.hypot(first_x, first_y)
        second_length = math.hypot(second_x, second_y)
        if first_length > 0.0 and second_length > 0.0:
            cosine = max(
                -1.0,
                min(
                    1.0,
                    (first_x * second_x + first_y * second_y)
                    / (first_length * second_length),
                ),
            )
            max_angle_change = max(
                max_angle_change,
                math.degrees(math.acos(cosine)),
            )

    return {
        "approach_correction_count": float(correction_count),
        "approach_deviation_px": round(max_deviation, 3),
        "approach_correction_ms": round(first_correction_ms, 3),
        "approach_angle_change_deg": round(max_angle_change, 3),
    }


def analyze_braking(
    velocities: list[dict[str, float]],
    accelerations: list[dict[str, float]],
    *,
    target_x: float,
    target_y: float,
    radius: float,
    click_down_ms: float,
) -> dict[str, float]:
    """Measure braking, target speed and pre-target steering corrections."""
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
            **_empty_approach(),
        }

    enriched: list[dict[str, float]] = [
        {
            **item,
            "distance_to_target_px": math.hypot(
                item["x"] - target_x,
                item["y"] - target_y,
            ),
        }
        for item in velocities
    ]

    peak_index = max(
        range(len(enriched)),
        key=lambda index: enriched[index]["speed_px_s"],
    )
    braking_index = peak_index
    peak_speed = max(enriched[peak_index]["speed_px_s"], 1.0)

    for index in range(peak_index, max(peak_index, len(enriched) - 2)):
        window = enriched[index : index + 4]
        if len(window) < 3:
            break
        speeds = [item["speed_px_s"] for item in window]
        falling_steps = sum(
            current < previous
            for previous, current in zip(speeds, speeds[1:])
        )
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
        (
            -item["accel_px_s2"]
            for item in accelerations
            if item["accel_px_s2"] < 0
        ),
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
        "speed_at_half_r_px_s": round(
            _nearest_speed(enriched, radius * 0.5),
            3,
        ),
        "final_100ms_speed_px_s": round(_mean(final_speeds), 3),
        "slowdown_ratio": (
            round(approach_speed / early_speed, 4)
            if early_speed > 0
            else 0.0
        ),
        **_analyze_approach_corrections(
            enriched,
            target_x=target_x,
            target_y=target_y,
            radius=radius,
        ),
    }
