from __future__ import annotations

from datetime import datetime
from typing import Any

from .metrics import stats

FEATURES = (
    "reaction_ms", "movement_time_ms", "click_delay_ms", "hold_ms", "click_error_px",
    "overshoot_px", "correction_count", "path_efficiency", "peak_speed_px_s",
)


def build_profile(trials: list[dict[str, Any]], free_holds: list[float]) -> dict[str, Any]:
    valid = [t for t in trials if isinstance(t.get("derived"), dict)]
    point_count = sum(len(t.get("points", [])) for t in valid)
    feature_stats = {name: stats([float(t["derived"].get(name, 0) or 0) for t in valid]) for name in FEATURES}
    feature_stats["click_hold_ms_free"] = stats(free_holds)
    coverage = min(1.0, len(valid) / 300)
    route_depth = min(1.0, point_count / 10_000)
    contexts = {(round(float(t["derived"].get("distance_px", 0)) / 100), int(t["target"].get("radius", 0))) for t in valid}
    context = min(1.0, len(contexts) / 20)
    misses = sum(1 for t in valid if t["derived"].get("miss"))
    quality = round(100 * (0.50 * coverage + 0.30 * route_depth + 0.20 * context))
    return {
        "schema_version": 3,
        "quality_percent": min(100, quality),
        "trial_count": len(valid),
        "point_count": point_count,
        "miss_count": misses,
        "features": feature_stats,
        "created_at": datetime.now().isoformat(),
    }
