from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .click_model import build_click_model
from .metrics import movement_points, stats
from .models import normalize_trials
from .schema import SCHEMA_VERSION

FEATURES = (
    "reaction_ms",
    "movement_time_ms",
    "click_delay_ms",
    "hold_ms",
    "click_error_px",
    "overshoot_px",
    "radial_overshoot_px",
    "directional_overshoot_px",
    "correction_count",
    "approach_correction_count",
    "approach_deviation_px",
    "approach_correction_ms",
    "approach_angle_change_deg",
    "entry_count",
    "exit_count",
    "path_efficiency",
    "peak_speed_px_s",
    "peak_speed_time_ms",
    "peak_accel_px_s2",
    "peak_decel_px_s2",
    "peak_jerk_px_s3",
    "braking_start_ms",
    "braking_distance_px",
    "braking_duration_ms",
    "target_approach_speed_px_s",
    "speed_at_entry_px_s",
    "speed_at_2r_px_s",
    "speed_at_1r_px_s",
    "speed_at_half_r_px_s",
    "final_100ms_speed_px_s",
    "slowdown_ratio",
)


def context_key(distance: float, radius: float, angle: float) -> str:
    distance_band = "short" if distance < 260 else "medium" if distance < 650 else "long"
    target_band = "small" if radius <= 18 else "medium" if radius <= 28 else "large"
    degrees = (math.degrees(angle) + 360.0) % 360.0
    directions = (
        "right",
        "down_right",
        "down",
        "down_left",
        "left",
        "up_left",
        "up",
        "up_right",
    )
    direction_index = int(((degrees + 22.5) % 360.0) // 45.0)
    return f"{distance_band}:{target_band}:{directions[direction_index]}"


def quality_reason(trial: dict[str, Any]) -> str | None:
    if trial.get("capture_mode", "normal") != "normal":
        return "test_mode"
    derived = trial.get("derived")
    points = trial.get("points", [])
    if not isinstance(derived, dict) or not isinstance(points, list) or len(points) < 3:
        return "incomplete"
    if float(derived.get("movement_time_ms", 0) or 0) > 10000:
        return "duration"
    efficiency = float(derived.get("path_efficiency", 0) or 0)
    if efficiency < 0.15 or efficiency > 1.05:
        return "implausible_path"
    if float(derived.get("peak_speed_px_s", 0) or 0) > 30000:
        return "speed_spike"
    previous: dict[str, Any] | None = None
    for point in points:
        x = float(point.get("x", 0))
        y = float(point.get("y", 0))
        if not (-120 <= x <= 2040 and -120 <= y <= 1200):
            return "outside_arena"
        if previous is not None:
            dt = float(point.get("t_ms", 0)) - float(previous.get("t_ms", 0))
            jump = math.hypot(
                x - float(previous.get("x", 0)),
                y - float(previous.get("y", 0)),
            )
            if dt < 25 and jump > 600:
                return "sample_jump"
        previous = point
    return None


def _feature_stats(trials: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result = {
        name: stats(
            [float(trial["derived"].get(name, 0) or 0) for trial in trials]
        )
        for name in FEATURES
    }
    positive_overshoots = [
        float(trial["derived"].get("overshoot_px", 0) or 0)
        for trial in trials
        if float(trial["derived"].get("overshoot_px", 0) or 0) > 0.25
    ]
    result["overshoot_positive_px"] = stats(positive_overshoots)
    return result


def _stationary_ratio(points: list[dict[str, float]]) -> float:
    if len(points) < 2:
        return 0.0
    stationary = 0
    for first, second in zip(points, points[1:]):
        if math.hypot(
            float(second["x"]) - float(first["x"]),
            float(second["y"]) - float(first["y"]),
        ) < 0.35:
            stationary += 1
    return stationary / max(1, len(points) - 1)


def _route_template(
    trial: dict[str, Any],
    max_points: int = 96,
) -> dict[str, Any] | None:
    target = trial["target"]
    start = trial["start"]
    click = trial["click"]
    route = movement_points(trial["points"], click, start)
    if len(route) < 3:
        return None

    sx, sy = float(start["x"]), float(start["y"])
    tx, ty = float(target["x"]), float(target["y"])
    click_x, click_y = float(route[-1]["x"]), float(route[-1]["y"])

    target_dx, target_dy = tx - sx, ty - sy
    target_distance = math.hypot(target_dx, target_dy)
    if target_distance < 3:
        return None
    target_angle = math.atan2(target_dy, target_dx)

    click_dx, click_dy = click_x - sx, click_y - sy
    click_distance = math.hypot(click_dx, click_dy)
    if click_distance < 3:
        return None
    ux, uy = click_dx / click_distance, click_dy / click_distance
    perpendicular_x, perpendicular_y = -uy, ux

    derived = trial["derived"]
    reaction_ms = max(0.0, float(derived.get("reaction_ms", 0) or 0))
    click_down_ms = max(
        reaction_ms + 1.0,
        float(click.get("down_t_ms", route[-1]["t_ms"]) or route[-1]["t_ms"]),
    )
    movement_duration_ms = max(1.0, click_down_ms - reaction_ms)

    active = [point for point in route if float(point["t_ms"]) >= reaction_ms]
    if not active:
        active = [route[-1]]
    stride = max(1, math.ceil(len(active) / max_points))
    selected = active[::stride]
    if selected[-1] != active[-1]:
        selected.append(active[-1])

    normalized_points: list[dict[str, float]] = [
        {"t": 0.0, "along": 0.0, "side": 0.0}
    ]
    for point in selected:
        relative_x = float(point["x"]) - sx
        relative_y = float(point["y"]) - sy
        normalized_t = max(
            0.0,
            min(
                1.0,
                (float(point["t_ms"]) - reaction_ms) / movement_duration_ms,
            ),
        )
        normalized = {
            "t": round(normalized_t, 6),
            "along": round(
                (relative_x * ux + relative_y * uy) / click_distance,
                6,
            ),
            "side": round(
                (
                    relative_x * perpendicular_x
                    + relative_y * perpendicular_y
                )
                / click_distance,
                6,
            ),
        }
        previous = normalized_points[-1]
        if normalized["t"] <= previous["t"]:
            continue
        spatial_change = math.hypot(
            normalized["along"] - previous["along"],
            normalized["side"] - previous["side"],
        )
        if spatial_change < 0.0009 and normalized["t"] - previous["t"] < 0.075:
            continue
        normalized_points.append(normalized)

    if len(normalized_points) < 3:
        return None
    if normalized_points[-1]["t"] < 1.0:
        normalized_points.append({"t": 1.0, "along": 1.0, "side": 0.0})
    else:
        normalized_points[-1] = {"t": 1.0, "along": 1.0, "side": 0.0}

    efficiency = float(derived.get("path_efficiency", 0) or 0)
    stationary_ratio = _stationary_ratio(active)
    max_side_ratio = max(abs(point["side"]) for point in normalized_points)
    min_along_ratio = min(point["along"] for point in normalized_points)
    max_along_ratio = max(point["along"] for point in normalized_points)
    quality = 1.0
    quality -= max(0.0, 0.78 - efficiency) * 1.7
    quality -= min(0.35, stationary_ratio * 0.70)
    quality -= max(0.0, max_side_ratio - 0.22) * 1.8
    quality -= max(0.0, -0.18 - min_along_ratio) * 1.2
    quality -= max(0.0, max_along_ratio - 1.35) * 1.2
    quality = max(0.05, min(1.0, quality))

    return {
        "shape_version": 1,
        "context": context_key(
            target_distance,
            float(target["radius"]),
            target_angle,
        ),
        "distance_px": round(target_distance, 3),
        "click_distance_px": round(click_distance, 3),
        "radius": float(target["radius"]),
        "angle": round(target_angle, 6),
        "duration_ms": round(movement_duration_ms, 3),
        "reaction_ms": round(reaction_ms, 3),
        "click_delay_ms": round(
            float(derived.get("click_delay_ms", 0) or 0),
            3,
        ),
        "hold_ms": round(float(derived.get("hold_ms", 0) or 0), 3),
        "path_efficiency": round(efficiency, 4),
        "slowdown_ratio": round(
            float(derived.get("slowdown_ratio", 0) or 0),
            4,
        ),
        "stationary_ratio": round(stationary_ratio, 4),
        "max_side_ratio": round(max_side_ratio, 4),
        "quality_score": round(quality, 4),
        "points": normalized_points,
    }


def build_personal_profile(
    trials: list[dict[str, Any]],
    free_holds: list[float],
) -> dict[str, Any]:
    normalized = normalize_trials(trials)
    accepted: list[dict[str, Any]] = []
    rejected_reasons: dict[str, int] = {}
    for trial in normalized:
        reason = quality_reason(trial)
        if reason is None:
            accepted.append(trial)
        else:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    groups: dict[str, list[dict[str, Any]]] = {}
    for trial in accepted:
        start = trial["start"]
        target = trial["target"]
        distance = float(trial["derived"].get("distance_px", 0) or 0)
        angle = math.atan2(
            float(target["y"]) - float(start["y"]),
            float(target["x"]) - float(start["x"]),
        )
        groups.setdefault(
            context_key(distance, float(target["radius"]), angle),
            [],
        ).append(trial)

    contexts: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        contexts[key] = {
            "trial_count": len(group),
            "features": _feature_stats(group),
            "overshoot_rate": round(
                sum(
                    float(trial["derived"].get("overshoot_px", 0) or 0) > 0.25
                    for trial in group
                )
                / len(group),
                4,
            ),
            "correction_rate": round(
                sum(
                    float(trial["derived"].get("correction_count", 0) or 0) > 0
                    for trial in group
                )
                / len(group),
                4,
            ),
            "miss_rate": round(
                sum(bool(trial.get("miss_clicks")) for trial in group)
                / len(group),
                4,
            ),
        }

    templates = [
        template
        for trial in accepted
        if (template := _route_template(trial)) is not None
    ]
    feature_stats = _feature_stats(accepted)
    feature_stats["click_hold_ms_free"] = stats(free_holds)
    context_depth = sum(
        1
        for context in contexts.values()
        if context["trial_count"] >= 8
    )
    quality = round(
        100 * min(1.0, len(accepted) / 300) * 0.42
        + 100 * min(1.0, len(templates) / 220) * 0.25
        + 100 * min(1.0, context_depth / 18) * 0.33
    )
    trial_count = max(1, len(accepted))
    miss_count = sum(len(trial.get("miss_clicks", [])) for trial in accepted)
    overshoot_rate = sum(
        float(trial["derived"].get("overshoot_px", 0) or 0) > 0.25
        for trial in accepted
    ) / trial_count
    correction_rate = sum(
        float(trial["derived"].get("correction_count", 0) or 0) > 0
        for trial in accepted
    ) / trial_count
    return {
        "schema_version": SCHEMA_VERSION,
        "quality_percent": min(100, quality),
        "trial_count": len(accepted),
        "raw_trial_count": len(normalized),
        "rejected_trial_count": len(normalized) - len(accepted),
        "rejected_reasons": rejected_reasons,
        "point_count": sum(len(trial["points"]) for trial in accepted),
        "miss_count": miss_count,
        "miss_rate": round(miss_count / trial_count, 4),
        "overshoot_rate": round(overshoot_rate, 4),
        "correction_rate": round(correction_rate, 4),
        "features": feature_stats,
        "contexts": contexts,
        "route_templates": templates[-500:],
        "click_model": build_click_model(accepted),
        "created_at": datetime.now().isoformat(),
    }
