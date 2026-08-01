from __future__ import annotations

import math
import random
from typing import Any

from .generator import simulate as base_simulate
from .metrics import derive_trial


def _first_entry(points: list[dict[str, float]], target: dict[str, Any]) -> float | None:
    tx = float(target["x"])
    ty = float(target["y"])
    radius = float(target["radius"])
    for point in points:
        if math.hypot(float(point["x"]) - tx, float(point["y"]) - ty) <= radius:
            return float(point["t_ms"])
    return None


def _smooth_noise(anchors: list[float], u: float) -> float:
    position = max(0.0, min(0.999999, u)) * (len(anchors) - 1)
    index = int(position)
    local = position - index
    eased = local * local * (3.0 - 2.0 * local)
    return anchors[index] * (1.0 - eased) + anchors[index + 1] * eased


def _continuous_route_cloud(
    points: list[dict[str, float]],
    start: dict[str, Any],
    click: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, float]]:
    if len(points) < 4:
        return points
    sx, sy = float(start["x"]), float(start["y"])
    ex, ey = float(click["x"]), float(click["y"])
    dx, dy = ex - sx, ey - sy
    distance = math.hypot(dx, dy)
    if distance < 20.0:
        return points
    px, py = -dy / distance, dx / distance
    active = [point for point in points if math.hypot(float(point["x"]) - sx, float(point["y"]) - sy) > 0.01]
    if not active:
        return points
    start_t = float(active[0]["t_ms"])
    end_t = max(start_t + 1.0, float(points[-1]["t_ms"]))
    amplitude = min(54.0, max(3.0, distance * rng.uniform(0.012, 0.045)))
    bias = rng.gauss(0.0, amplitude * 0.35)
    anchors = [rng.gauss(0.0, 1.0) for _ in range(7)]

    warped: list[dict[str, float]] = []
    for point in points:
        t_ms = float(point["t_ms"])
        x, y = float(point["x"]), float(point["y"])
        if t_ms <= start_t:
            warped.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})
            continue
        u = max(0.0, min(1.0, (t_ms - start_t) / (end_t - start_t)))
        envelope = math.sin(math.pi * u) ** 1.25
        offset = envelope * (bias + _smooth_noise(anchors, u) * amplitude * 0.62)
        warped.append(
            {
                "t_ms": round(t_ms, 3),
                "x": round(x + px * offset, 3),
                "y": round(y + py * offset, 3),
            }
        )
    warped[0] = {"t_ms": float(points[0]["t_ms"]), "x": sx, "y": sy}
    warped[-1] = {"t_ms": float(points[-1]["t_ms"]), "x": ex, "y": ey}
    return warped


def _compact_miss_recovery(trial: dict[str, Any], rng: random.Random) -> None:
    misses = trial.get("miss_clicks", [])
    if not isinstance(misses, list) or not misses:
        return
    miss = misses[0]
    points = trial["points"]
    click = trial["click"]
    miss_up = float(miss["up_t_ms"])
    before = [point for point in points if float(point["t_ms"]) <= miss_up]
    if not before:
        before = [points[0]]
    sx, sy = float(miss["x"]), float(miss["y"])
    ex, ey = float(click["x"]), float(click["y"])
    duration = rng.uniform(70.0, 125.0)
    dx, dy = ex - sx, ey - sy
    length = max(1.0, math.hypot(dx, dy))
    px, py = -dy / length, dx / length
    curve = rng.gauss(0.0, min(2.5, length * 0.08))
    for index in range(1, 9):
        u = index / 8
        ease = u * u * (3.0 - 2.0 * u)
        side = math.sin(math.pi * u) * curve
        before.append(
            {
                "t_ms": round(miss_up + duration * u, 3),
                "x": round(sx + dx * ease + px * side, 3),
                "y": round(sy + dy * ease + py * side, 3),
            }
        )
    old_down = float(click["down_t_ms"])
    hold = max(25.0, float(click["up_t_ms"]) - old_down)
    click_down = miss_up + duration + rng.uniform(18.0, 65.0)
    click["down_t_ms"] = round(click_down, 3)
    click["up_t_ms"] = round(click_down + hold, 3)
    trial["points"] = before


def _trim_click_delay(trial: dict[str, Any], rng: random.Random) -> None:
    points = trial["points"]
    target = trial["target"]
    click = trial["click"]
    entry = _first_entry(points, target)
    if entry is None:
        return
    current = float(click["down_t_ms"]) - entry
    lower = 28.0
    upper = 430.0 if not trial.get("miss_clicks") else 520.0
    if current > upper:
        desired = rng.uniform(220.0, upper)
    elif current < lower:
        desired = rng.uniform(lower, 80.0)
    else:
        desired = current
    new_down = entry + desired
    old_down = float(click["down_t_ms"])
    hold = max(25.0, float(click["up_t_ms"]) - old_down)
    click["down_t_ms"] = round(new_down, 3)
    click["up_t_ms"] = round(new_down + hold, 3)
    kept = [point for point in points if float(point["t_ms"]) < new_down]
    kept.append({"t_ms": round(new_down, 3), "x": float(click["x"]), "y": float(click["y"])})
    trial["points"] = kept


def _limit_speed(trial: dict[str, Any], cap_px_s: float = 12000.0) -> None:
    points = trial["points"]
    if len(points) < 2:
        return
    shift = 0.0
    previous = points[0]
    for point in points[1:]:
        t_ms = float(point["t_ms"]) + shift
        distance = math.hypot(float(point["x"]) - float(previous["x"]), float(point["y"]) - float(previous["y"]))
        minimum_dt = distance / cap_px_s * 1000.0
        actual_dt = t_ms - float(previous["t_ms"])
        if actual_dt < minimum_dt:
            extra = minimum_dt - actual_dt
            shift += extra
            t_ms += extra
        point["t_ms"] = round(t_ms, 3)
        previous = point
    if shift > 0:
        click = trial["click"]
        click["down_t_ms"] = round(float(click["down_t_ms"]) + shift, 3)
        click["up_t_ms"] = round(float(click["up_t_ms"]) + shift, 3)
        for miss in trial.get("miss_clicks", []):
            miss["down_t_ms"] = round(float(miss["down_t_ms"]) + shift, 3)
            miss["up_t_ms"] = round(float(miss["up_t_ms"]) + shift, 3)


def _rederive(trial: dict[str, Any]) -> None:
    trial["derived"] = derive_trial(
        trial["target"], trial["start"], trial["points"], trial["click"]
    )


def simulate(
    plan: dict[str, Any],
    profile: dict[str, Any],
    seed: int | None = None,
) -> list[dict[str, Any]]:
    trials = base_simulate(plan, profile, seed)
    rng = random.Random((seed or int(plan.get("seed", 1))) ^ 0x5A17C0DE)
    for trial in trials:
        local = random.Random(rng.randrange(1, 2**31 - 1))
        trial["points"] = _continuous_route_cloud(
            trial["points"], trial["start"], trial["click"], local
        )
        _compact_miss_recovery(trial, local)
        _trim_click_delay(trial, local)
        _limit_speed(trial)
        _rederive(trial)
    return trials
