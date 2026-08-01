from __future__ import annotations

import math
from typing import Any


def analyze_approach(
    target: dict[str, Any],
    start: dict[str, Any],
    points: list[dict[str, Any]],
    click: dict[str, Any],
) -> dict[str, float | int]:
    """Measure meaningful steering corrections before first target entry.

    A correction is counted when lateral movement changes direction after a
    meaningful deviation from the ideal start-to-target line. Movement beyond
    the target is deliberately excluded; that belongs to overshoot metrics.
    """
    try:
        sx, sy = float(start["x"]), float(start["y"])
        tx, ty = float(target["x"]), float(target["y"])
        radius = float(target.get("radius", 18.0))
        click_down = float(click.get("down_t_ms", 0.0) or 0.0)
    except (KeyError, TypeError, ValueError, AttributeError):
        return _empty()

    dx, dy = tx - sx, ty - sy
    distance = math.hypot(dx, dy)
    if distance < 1.0:
        return _empty()

    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    cleaned: list[tuple[float, float, float]] = []
    for point in points:
        try:
            t = float(point["t_ms"])
            x = float(point["x"])
            y = float(point["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if click_down and t > click_down:
            continue
        projection = (x - sx) * ux + (y - sy) * uy
        radial = math.hypot(x - tx, y - ty)
        if projection > distance + radius or radial <= radius:
            break
        lateral = (x - sx) * px + (y - sy) * py
        cleaned.append((t, projection, lateral))

    if len(cleaned) < 5:
        return _empty()

    threshold = max(3.0, radius * 0.12)
    max_deviation = max(abs(item[2]) for item in cleaned)
    correction_count = 0
    first_correction_ms = 0.0
    recovery_ms = 0.0
    max_angle_change = 0.0
    previous_sign = 0
    deviation_peak_time = 0.0

    for index in range(1, len(cleaned) - 1):
        before = cleaned[index - 1]
        current = cleaned[index]
        after = cleaned[index + 1]
        lateral_velocity_before = current[2] - before[2]
        lateral_velocity_after = after[2] - current[2]
        sign_before = 1 if lateral_velocity_before > 0 else -1 if lateral_velocity_before < 0 else 0
        sign_after = 1 if lateral_velocity_after > 0 else -1 if lateral_velocity_after < 0 else 0

        if abs(current[2]) >= threshold:
            deviation_peak_time = current[0]
        if sign_before and sign_after and sign_before != sign_after and abs(current[2]) >= threshold:
            if previous_sign != sign_after:
                correction_count += 1
                previous_sign = sign_after
                if first_correction_ms == 0.0:
                    first_correction_ms = current[0]
                if deviation_peak_time:
                    recovery_ms = max(recovery_ms, current[0] - deviation_peak_time)

            v1x, v1y = current[1] - before[1], current[2] - before[2]
            v2x, v2y = after[1] - current[1], after[2] - current[2]
            len1, len2 = math.hypot(v1x, v1y), math.hypot(v2x, v2y)
            if len1 > 0 and len2 > 0:
                cosine = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (len1 * len2)))
                max_angle_change = max(max_angle_change, math.degrees(math.acos(cosine)))

    return {
        "approach_correction_count": correction_count,
        "approach_deviation_px": round(max_deviation, 3),
        "approach_correction_ms": round(first_correction_ms, 3),
        "approach_recovery_ms": round(recovery_ms, 3),
        "approach_angle_change_deg": round(max_angle_change, 3),
    }


def enrich_derived(
    derived: dict[str, Any],
    target: dict[str, Any],
    start: dict[str, Any],
    points: list[dict[str, Any]],
    click: dict[str, Any],
) -> dict[str, Any]:
    output = dict(derived)
    output.update(analyze_approach(target, start, points, click))
    output["correction_count"] = int(output.get("correction_count", 0) or 0) + int(
        output.get("approach_correction_count", 0) or 0
    )
    return output


def _empty() -> dict[str, float | int]:
    return {
        "approach_correction_count": 0,
        "approach_deviation_px": 0.0,
        "approach_correction_ms": 0.0,
        "approach_recovery_ms": 0.0,
        "approach_angle_change_deg": 0.0,
    }
