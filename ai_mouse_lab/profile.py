from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .metrics import stats

FEATURES = (
    "reaction_ms", "movement_time_ms", "click_delay_ms", "hold_ms", "click_error_px",
    "overshoot_px", "correction_count", "path_efficiency", "peak_speed_px_s",
)


def _route_template(trial: dict[str, Any], max_points: int = 96) -> dict[str, Any] | None:
    points = trial.get("points", [])
    target = trial.get("target", {})
    start = trial.get("start", {})
    if len(points) < 3:
        return None

    sx, sy = float(start.get("x", 0)), float(start.get("y", 0))
    tx, ty = float(target.get("x", 0)), float(target.get("y", 0))
    dx, dy = tx - sx, ty - sy
    distance = math.hypot(dx, dy)
    if distance < 1:
        return None

    ux, uy = dx / distance, dy / distance
    px, py = -uy, ux
    stride = max(1, math.ceil(len(points) / max_points))
    selected = points[::stride]
    if selected[-1] is not points[-1]:
        selected.append(points[-1])

    end_t = max(float(selected[-1].get("t_ms", 0)), 1.0)
    normalized = []
    previous_t = 0.0
    for point in selected:
        x, y = float(point["x"]), float(point["y"])
        t = max(previous_t, float(point.get("t_ms", previous_t)))
        rx, ry = x - sx, y - sy
        normalized.append({
            "t": round(t / end_t, 6),
            "along": round((rx * ux + ry * uy) / distance, 6),
            "side": round((rx * px + ry * py) / distance, 6),
        })
        previous_t = t

    click = trial.get("click", {})
    click_rx = float(click.get("x", tx)) - tx
    click_ry = float(click.get("y", ty)) - ty
    derived = trial.get("derived", {})
    return {
        "distance_px": round(distance, 3),
        "radius": int(target.get("radius", 18)),
        "angle": round(math.atan2(dy, dx), 6),
        "duration_ms": round(end_t, 3),
        "reaction_ms": round(float(derived.get("reaction_ms", 0) or 0), 3),
        "click_delay_ms": round(float(derived.get("click_delay_ms", 0) or 0), 3),
        "hold_ms": round(float(derived.get("hold_ms", 80) or 80), 3),
        "click_along_px": round(click_rx * ux + click_ry * uy, 3),
        "click_side_px": round(click_rx * px + click_ry * py, 3),
        "miss_clicks": len(trial.get("miss_clicks", [])),
        "points": normalized,
    }


def build_profile(trials: list[dict[str, Any]], free_holds: list[float]) -> dict[str, Any]:
    valid = [t for t in trials if isinstance(t.get("derived"), dict)]
    point_count = sum(len(t.get("points", [])) for t in valid)
    feature_stats = {name: stats([float(t["derived"].get(name, 0) or 0) for t in valid]) for name in FEATURES}
    feature_stats["click_hold_ms_free"] = stats(free_holds)
    coverage = min(1.0, len(valid) / 300)
    route_depth = min(1.0, point_count / 10_000)
    contexts = {(round(float(t["derived"].get("distance_px", 0)) / 100), int(t["target"].get("radius", 0))) for t in valid}
    context = min(1.0, len(contexts) / 20)
    misses = sum(len(t.get("miss_clicks", [])) for t in valid)
    templates = [template for trial in valid if (template := _route_template(trial)) is not None]
    quality = round(100 * (0.50 * coverage + 0.30 * route_depth + 0.20 * context))
    return {
        "schema_version": 4,
        "quality_percent": min(100, quality),
        "trial_count": len(valid),
        "point_count": point_count,
        "miss_count": misses,
        "features": feature_stats,
        "route_templates": templates[-500:],
        "created_at": datetime.now().isoformat(),
    }
