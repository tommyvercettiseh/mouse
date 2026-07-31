from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any

from .metrics import stats
from .v06 import _personal_route

FEATURES = (
    "reaction_ms", "movement_time_ms", "click_delay_ms", "hold_ms", "click_error_px",
    "overshoot_px", "directional_overshoot_px", "correction_count", "entry_count", "exit_count",
    "path_efficiency", "peak_speed_px_s", "peak_accel_px_s2", "peak_jerk_px_s3", "braking_start_ms",
)


def context_key(distance: float, radius: float, angle: float) -> str:
    distance_band = "short" if distance < 260 else "medium" if distance < 650 else "long"
    target_band = "small" if radius <= 18 else "medium" if radius <= 28 else "large"
    degrees = (math.degrees(angle) + 360.0) % 360.0
    if degrees < 22.5 or degrees >= 337.5:
        direction = "right"
    elif degrees < 67.5:
        direction = "down_right"
    elif degrees < 112.5:
        direction = "down"
    elif degrees < 157.5:
        direction = "down_left"
    elif degrees < 202.5:
        direction = "left"
    elif degrees < 247.5:
        direction = "up_left"
    elif degrees < 292.5:
        direction = "up"
    else:
        direction = "up_right"
    return f"{distance_band}:{target_band}:{direction}"


def _quality_reason(trial: dict[str, Any]) -> str | None:
    if trial.get("capture_mode", "normal") != "normal":
        return "test_mode"
    derived = trial.get("derived")
    points = trial.get("points", [])
    if not isinstance(derived, dict) or len(points) < 3:
        return "incomplete"
    if float(derived.get("movement_time_ms", 0) or 0) > 10000:
        return "duration"
    if float(derived.get("path_efficiency", 0) or 0) < 0.15:
        return "implausible_path"
    if float(derived.get("peak_speed_px_s", 0) or 0) > 30000:
        return "speed_spike"
    previous = None
    for point in points:
        x, y = float(point.get("x", 0)), float(point.get("y", 0))
        if not (-120 <= x <= 2040 and -120 <= y <= 1200):
            return "outside_arena"
        if previous is not None:
            dt = float(point.get("t_ms", 0)) - float(previous.get("t_ms", 0))
            jump = math.hypot(x - float(previous.get("x", 0)), y - float(previous.get("y", 0)))
            if dt < 25 and jump > 600:
                return "sample_jump"
        previous = point
    return None


def _route_template(trial: dict[str, Any], max_points: int = 96) -> dict[str, Any] | None:
    points, target, start = trial.get("points", []), trial.get("target", {}), trial.get("start", {})
    if len(points) < 3:
        return None
    sx, sy = float(start.get("x", 0)), float(start.get("y", 0))
    tx, ty = float(target.get("x", 0)), float(target.get("y", 0))
    dx, dy = tx - sx, ty - sy
    distance = math.hypot(dx, dy)
    if distance < 3:
        return None
    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    stride = max(1, math.ceil(len(points) / max_points))
    selected = points[::stride]
    if selected[-1] != points[-1]:
        selected.append(points[-1])
    end_t = max(float(selected[-1].get("t_ms", 0)), 1.0)
    normalized = []
    for point in selected:
        rx, ry = float(point["x"]) - sx, float(point["y"]) - sy
        normalized.append({
            "t": round(float(point.get("t_ms", 0)) / end_t, 6),
            "along": round((rx * ux + ry * uy) / distance, 6),
            "side": round((rx * px + ry * py) / distance, 6),
        })
    click, derived = trial.get("click", {}), trial.get("derived", {})
    click_rx, click_ry = float(click.get("x", tx)) - tx, float(click.get("y", ty)) - ty
    angle = math.atan2(dy, dx)
    return {
        "context": context_key(distance, float(target.get("radius", 18)), angle),
        "distance_px": round(distance, 3), "radius": int(target.get("radius", 18)), "angle": round(angle, 6),
        "duration_ms": round(end_t, 3), "reaction_ms": round(float(derived.get("reaction_ms", 0) or 0), 3),
        "click_delay_ms": round(float(derived.get("click_delay_ms", 0) or 0), 3),
        "hold_ms": round(float(derived.get("hold_ms", 80) or 80), 3),
        "click_along_px": round(click_rx * ux + click_ry * uy, 3),
        "click_side_px": round(click_rx * px + click_ry * py, 3),
        "path_efficiency": round(float(derived.get("path_efficiency", 0.9) or 0.9), 4),
        "points": normalized,
    }


def _feature_stats(trials: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {name: stats([float(t["derived"].get(name, 0) or 0) for t in trials]) for name in FEATURES}


def build_personal_profile(trials: list[dict[str, Any]], free_holds: list[float]) -> dict[str, Any]:
    accepted, rejected = [], {}
    for trial in trials:
        reason = _quality_reason(trial)
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
        else:
            accepted.append(trial)

    groups: dict[str, list[dict[str, Any]]] = {}
    for trial in accepted:
        d = trial["derived"]
        start, target = trial["start"], trial["target"]
        angle = math.atan2(float(target["y"]) - float(start["y"]), float(target["x"]) - float(start["x"]))
        key = context_key(float(d.get("distance_px", 0)), float(target.get("radius", 18)), angle)
        groups.setdefault(key, []).append(trial)

    contexts = {}
    for key, group in groups.items():
        overshoots = [float(t["derived"].get("overshoot_px", 0) or 0) for t in group]
        contexts[key] = {
            "trial_count": len(group),
            "features": _feature_stats(group),
            "overshoot_rate": round(sum(v > 0.25 for v in overshoots) / len(group), 4),
            "correction_rate": round(sum(float(t["derived"].get("correction_count", 0) or 0) > 0 for t in group) / len(group), 4),
            "miss_rate": round(sum(len(t.get("miss_clicks", [])) > 0 for t in group) / len(group), 4),
        }

    templates = [template for trial in accepted if (template := _route_template(trial)) is not None]
    features = _feature_stats(accepted)
    features["click_hold_ms_free"] = stats(free_holds)
    context_depth = sum(1 for value in contexts.values() if value["trial_count"] >= 8)
    quality = round(100 * min(1.0, len(accepted) / 300) * 0.42 + 100 * min(1.0, len(templates) / 220) * 0.25 + 100 * min(1.0, context_depth / 18) * 0.33)
    overshoots = [float(t["derived"].get("overshoot_px", 0) or 0) for t in accepted]
    return {
        "schema_version": 6,
        "quality_percent": min(100, quality),
        "trial_count": len(accepted),
        "raw_trial_count": len(trials),
        "rejected_trial_count": len(trials) - len(accepted),
        "rejected_reasons": rejected,
        "point_count": sum(len(t.get("points", [])) for t in accepted),
        "miss_count": sum(len(t.get("miss_clicks", [])) for t in accepted),
        "overshoot_rate": round(sum(v > 0.25 for v in overshoots) / max(len(accepted), 1), 4),
        "features": features,
        "contexts": contexts,
        "route_templates": templates[-500:],
        "created_at": datetime.now().isoformat(),
    }


def _effective_profile(profile: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    sx, sy = map(float, item["start"]); tx, ty = map(float, item["target"])
    distance = math.hypot(tx - sx, ty - sy); angle = math.atan2(ty - sy, tx - sx)
    key = context_key(distance, float(item["radius"]), angle)
    context = profile.get("contexts", {}).get(key)
    if not context or int(context.get("trial_count", 0)) < 5:
        return profile
    merged = dict(profile)
    merged["features"] = {**profile.get("features", {}), **context.get("features", {})}
    merged["miss_count"] = round(float(context.get("miss_rate", 0)) * max(int(context.get("trial_count", 1)), 1))
    merged["trial_count"] = max(int(context.get("trial_count", 1)), 1)
    templates = [t for t in profile.get("route_templates", []) if t.get("context") == key]
    if templates:
        merged["route_templates"] = templates
    return merged


def contextual_simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(plan["seed"]) + 1)
    session_scale = rng.uniform(0.94, 1.08)
    return [_personal_route(item, _effective_profile(profile, item), rng, session_scale) for item in plan["targets"]]
