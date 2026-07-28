from __future__ import annotations

import math
import statistics
from typing import Any


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * p
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    fraction = idx - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {k: 0.0 for k in ("mean", "median", "stdev", "p10", "p90", "min", "max")}
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
    if window < 1 or len(points) <= 2:
        return [{"t_ms": float(p["t_ms"]), "x": float(p["x"]), "y": float(p["y"])} for p in points]
    radius = window // 2
    out: list[dict[str, float]] = []
    for i, point in enumerate(points):
        lo, hi = max(0, i - radius), min(len(points), i + radius + 1)
        chunk = points[lo:hi]
        out.append({
            "t_ms": float(point["t_ms"]),
            "x": sum(float(p["x"]) for p in chunk) / len(chunk),
            "y": sum(float(p["y"]) for p in chunk) / len(chunk),
        })
    return out


def derive_trial(target: dict[str, float], start: dict[str, float], points: list[dict[str, Any]], click: dict[str, Any]) -> dict[str, Any]:
    if len(points) < 2:
        raise ValueError("At least two route points are required")
    clean = smooth_points(points)
    tx, ty, radius = float(target["x"]), float(target["y"]), float(target["radius"])
    sx, sy = float(start["x"]), float(start["y"])
    straight = math.hypot(tx - sx, ty - sy)
    path = 0.0
    speeds: list[tuple[float, float]] = []
    accelerations: list[tuple[float, float]] = []
    for a, b in zip(clean, clean[1:]):
        dt = max(0.001, (b["t_ms"] - a["t_ms"]) / 1000.0)
        dist = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
        path += dist
        speeds.append((b["t_ms"], dist / dt))
    for a, b in zip(speeds, speeds[1:]):
        dt = max(0.001, (b[0] - a[0]) / 1000.0)
        accelerations.append((b[0], (b[1] - a[1]) / dt))
    jerks: list[float] = []
    for a, b in zip(accelerations, accelerations[1:]):
        dt = max(0.001, (b[0] - a[0]) / 1000.0)
        jerks.append((b[1] - a[1]) / dt)

    first_move_ms = 0.0
    for p in clean:
        if math.hypot(p["x"] - sx, p["y"] - sy) >= 3.0:
            first_move_ms = p["t_ms"]
            break

    inside = [math.hypot(p["x"] - tx, p["y"] - ty) <= radius for p in clean]
    click_x = float(click.get("x", clean[-1]["x"]))
    click_y = float(click.get("y", clean[-1]["y"]))
    if math.hypot(click_x - tx, click_y - ty) <= radius and not inside[-1]:
        inside[-1] = True
    first_entry_idx = next((i for i, value in enumerate(inside) if value), None)
    first_entry_ms = clean[first_entry_idx]["t_ms"] if first_entry_idx is not None else None
    entry_count = sum(1 for prev, cur in zip(inside, inside[1:]) if not prev and cur)
    exit_count = sum(1 for prev, cur in zip(inside, inside[1:]) if prev and not cur)
    correction_count = max(0, entry_count - 1)

    overshoot = 0.0
    if first_entry_idx is not None:
        for p in clean[first_entry_idx:]:
            overshoot = max(overshoot, max(0.0, math.hypot(p["x"] - tx, p["y"] - ty) - radius))

    click_down_ms = float(click.get("down_t_ms") or clean[-1]["t_ms"])
    click_up_ms = float(click.get("up_t_ms") or click_down_ms)
    braking_start_ms = max(speeds, key=lambda item: item[1])[0] if speeds else 0.0

    return {
        "reaction_ms": round(first_move_ms, 3),
        "movement_time_ms": round(click_down_ms, 3),
        "first_entry_ms": round(first_entry_ms, 3) if first_entry_ms is not None else None,
        "click_delay_ms": round(max(0.0, click_down_ms - (first_entry_ms or click_down_ms)), 3),
        "hold_ms": round(max(0.0, click_up_ms - click_down_ms), 3),
        "distance_px": round(straight, 3),
        "path_length_px": round(path, 3),
        "path_efficiency": round(straight / path, 4) if path > 0 else 0.0,
        "click_error_px": round(math.hypot(click_x - tx, click_y - ty), 3),
        "peak_speed_px_s": round(max((v for _, v in speeds), default=0.0), 3),
        "peak_accel_px_s2": round(max((abs(v) for _, v in accelerations), default=0.0), 3),
        "peak_jerk_px_s3": round(max((abs(v) for v in jerks), default=0.0), 3),
        "braking_start_ms": round(braking_start_ms, 3),
        "overshoot_px": round(overshoot, 3),
        "correction_count": correction_count,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "miss": first_entry_idx is None,
    }
