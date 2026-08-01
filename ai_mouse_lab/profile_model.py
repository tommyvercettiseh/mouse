from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .click_model import build_click_model
from .metrics import stats
from .schema import SCHEMA_VERSION, normalize_trials

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
            jump = math.hypot(x - float(previous.get("x", 0)), y - float(previous.get("y", 0)))
            if dt < 25 and jump > 600:
                return "sample_jump"
        previous = point
    return None


def _feature_stats(trials: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        name: stats([float(trial["derived"].get(name, 0) or 0) for trial in trials])
        for name in FEATURES
    }


def _route_template(trial: dict[str, Any], max_points: int = 96) -> dict[str, Any] | None:
    points = trial["points"]
    target = trial["target"]
    start = trial["start"]
    if len(points) < 3:
        return None
    sx, sy = float(start["x"]), float(start["y"])
    tx, ty = float(target["x"]), float(target["y"])
    dx, dy = tx - sx, ty - sy
    distance = math.hypot(dx, dy)
    if distance < 3:
        return None
    ux, uy = dx / distance, dy / distance
    perpendicular_x, perpendicular_y = -uy, ux
    stride = max(1, math.ceil(len(points) / max_points))
    selected = points[::stride]
    if selected[-1] != points[-1]:
        selected.append(points[-1])
    duration_ms = max(float(selected[-1]["t_ms"]), 1.0)
    normalized_points: list[dict[str, float]] = []
    for point in selected:
        relative_x = float(point["x"]) - sx
        relative_y = float(point["y"]) - sy
        normalized_points.append(
            {
                "t": round(float(point["t_ms"]) / duration_ms, 6),
                "along": round((relative_x * ux + relative_y * uy) / distance, 6),
                "side": round((relative_x * perpendicular_x + relative_y * perpendicular_y) / distance, 6),
            }
        )
    derived = trial["derived"]
    angle = math.atan2(dy, dx)
    return {
        "context": context_key(distance, float(target["radius"]), angle),
        "distance_px": round(distance, 3),
        "radius": float(target["radius"]),
        "angle": round(angle, 6),
        "duration_ms": round(duration_ms, 3),
        "reaction_ms": round(float(derived.get("reaction_ms", 0) or 0), 3),
        "click_delay_ms": round(float(derived.get("click_delay_ms", 0) or 0), 3),
        "hold_ms": round(float(derived.get("hold_ms", 0) or 0), 3),
        "path_efficiency": round(float(derived.get("path_efficiency", 0) or 0), 4),
        "slowdown_ratio": round(float(derived.get("slowdown_ratio", 0) or 0), 4),
        "points": normalized_points,
    }


def build_personal_profile(trials: list[dict[str, Any]], free_holds: list[float]) -> dict[str, Any]:
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
        angle = math.atan2(float(target["y"]) - float(start["y"]), float(target["x"]) - float(start["x"]))
        groups.setdefault(context_key(distance, float(target["radius"]), angle), []).append(trial)

    contexts: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        contexts[key] = {
            "trial_count": len(group),
            "features": _feature_stats(group),
            "overshoot_rate": round(sum(float(trial["derived"].get("overshoot_px", 0) or 0) > 0.25 for trial in group) / len(group), 4),
            "correction_rate": round(sum(float(trial["derived"].get("correction_count", 0) or 0) > 0 for trial in group) / len(group), 4),
            "miss_rate": round(sum(bool(trial.get("miss_clicks")) for trial in group) / len(group), 4),
        }

    templates = [template for trial in accepted if (template := _route_template(trial)) is not None]
    feature_stats = _feature_stats(accepted)
    feature_stats["click_hold_ms_free"] = stats(free_holds)
    context_depth = sum(1 for context in contexts.values() if context["trial_count"] >= 8)
    quality = round(
        100 * min(1.0, len(accepted) / 300) * 0.42
        + 100 * min(1.0, len(templates) / 220) * 0.25
        + 100 * min(1.0, context_depth / 18) * 0.33
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "quality_percent": min(100, quality),
        "trial_count": len(accepted),
        "raw_trial_count": len(normalized),
        "rejected_trial_count": len(normalized) - len(accepted),
        "rejected_reasons": rejected_reasons,
        "point_count": sum(len(trial["points"]) for trial in accepted),
        "miss_count": sum(len(trial.get("miss_clicks", [])) for trial in accepted),
        "overshoot_rate": round(
            sum(float(trial["derived"].get("overshoot_px", 0) or 0) > 0.25 for trial in accepted) / max(1, len(accepted)),
            4,
        ),
        "features": feature_stats,
        "contexts": contexts,
        "route_templates": templates[-500:],
        "click_model": build_click_model(accepted),
        "created_at": datetime.now().isoformat(),
    }
