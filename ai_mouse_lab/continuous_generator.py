from __future__ import annotations

import math
import random
from typing import Any

from .generator import simulate as base_simulate
from .metrics import derive_trial

MIN_REACTION_MS = 55.0
RAW_SPEED_CAP_PX_S = 11000.0
MEASURED_SPEED_CAP_PX_S = 11500.0
MAX_GLOBAL_MISS_RATE = 0.10
MAX_MISS_RECOVERY_MS = 520.0


def _first_entry_index(points: list[dict[str, float]], target: dict[str, Any]) -> int | None:
    tx = float(target["x"])
    ty = float(target["y"])
    radius = float(target["radius"])
    for index, point in enumerate(points):
        if math.hypot(float(point["x"]) - tx, float(point["y"]) - ty) <= radius:
            return index
    return None


def _smooth_noise(anchors: list[float], u: float) -> float:
    position = max(0.0, min(0.999999, u)) * (len(anchors) - 1)
    index = int(position)
    local = position - index
    eased = local * local * (3.0 - 2.0 * local)
    return anchors[index] * (1.0 - eased) + anchors[index + 1] * eased


def _existing_lateral_ratio(points: list[dict[str, float]], start: dict[str, Any], click: dict[str, Any]) -> float:
    sx, sy = float(start["x"]), float(start["y"])
    ex, ey = float(click["x"]), float(click["y"])
    dx, dy = ex - sx, ey - sy
    distance = math.hypot(dx, dy)
    if distance < 1.0:
        return 0.0
    px, py = -dy / distance, dx / distance
    return max(
        abs((float(point["x"]) - sx) * px + (float(point["y"]) - sy) * py)
        for point in points
    ) / distance


def _asymmetric_envelope(u: float, peak: float, sharpness: float) -> float:
    u = max(0.0, min(1.0, u))
    peak = max(0.18, min(0.82, peak))
    local = u / peak if u <= peak else (1.0 - u) / (1.0 - peak)
    return math.sin(math.pi * 0.5 * max(0.0, min(1.0, local))) ** sharpness


def _continuous_route_cloud(
    points: list[dict[str, float]],
    start: dict[str, Any],
    click: dict[str, Any],
    target: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, float]]:
    if len(points) < 4:
        return points

    sx, sy = float(start["x"]), float(start["y"])
    ex, ey = float(click["x"]), float(click["y"])
    tx, ty = float(target["x"]), float(target["y"])
    radius = max(1.0, float(target["radius"]))
    dx, dy = ex - sx, ey - sy
    distance = math.hypot(dx, dy)
    if distance < 20.0:
        return points

    px, py = -dy / distance, dx / distance
    active = [p for p in points if math.hypot(float(p["x"]) - sx, float(p["y"]) - sy) > 0.01]
    if not active:
        return points

    start_t = float(active[0]["t_ms"])
    end_t = max(start_t + 1.0, float(points[-1]["t_ms"]))
    existing_ratio = _existing_lateral_ratio(points, start, click)
    available = max(0.16, min(1.0, 1.0 - existing_ratio / 0.10))
    amplitude = min(38.0, max(2.0, distance * rng.uniform(0.008, 0.026))) * available
    peak = rng.uniform(0.28, 0.72)
    sharpness = rng.uniform(1.0, 1.8)
    bias = rng.gauss(0.0, amplitude * 0.22)
    anchors = [rng.gauss(0.0, 1.0) for _ in range(8)]

    warped: list[dict[str, float]] = []
    for point in points:
        t_ms = float(point["t_ms"])
        x, y = float(point["x"]), float(point["y"])
        if t_ms <= start_t:
            warped.append({"t_ms": round(t_ms, 3), "x": round(x, 3), "y": round(y, 3)})
            continue

        u = max(0.0, min(1.0, (t_ms - start_t) / (end_t - start_t)))
        envelope = _asymmetric_envelope(u, peak, sharpness)
        target_distance = math.hypot(x - tx, y - ty)
        if target_distance <= radius * 1.5:
            target_fade = 0.0
        elif target_distance >= radius * 4.0:
            target_fade = 1.0
        else:
            local = (target_distance - radius * 1.5) / (radius * 2.5)
            target_fade = local * local * (3.0 - 2.0 * local)

        offset = envelope * target_fade * (bias + _smooth_noise(anchors, u) * amplitude * 0.58)
        warped.append({
            "t_ms": round(t_ms, 3),
            "x": round(x + px * offset, 3),
            "y": round(y + py * offset, 3),
        })

    warped[0] = {"t_ms": float(points[0]["t_ms"]), "x": sx, "y": sy}
    warped[-1] = {"t_ms": float(points[-1]["t_ms"]), "x": ex, "y": ey}
    return warped


def _first_motion_index(trial: dict[str, Any], threshold_px: float = 3.0) -> int | None:
    sx = float(trial["start"]["x"])
    sy = float(trial["start"]["y"])
    for index, point in enumerate(trial["points"]):
        if math.hypot(float(point["x"]) - sx, float(point["y"]) - sy) >= threshold_px:
            return index
    return None


def _enforce_reaction_floor(trial: dict[str, Any], minimum_ms: float = MIN_REACTION_MS) -> None:
    index = _first_motion_index(trial)
    if index is None:
        return
    current = float(trial["points"][index]["t_ms"])
    if current >= minimum_ms:
        return

    shift = minimum_ms - current
    for point in trial["points"][index:]:
        point["t_ms"] = round(float(point["t_ms"]) + shift, 3)
    trial["click"]["down_t_ms"] = round(float(trial["click"]["down_t_ms"]) + shift, 3)
    trial["click"]["up_t_ms"] = round(float(trial["click"]["up_t_ms"]) + shift, 3)
    for miss in trial.get("miss_clicks", []):
        miss["down_t_ms"] = round(float(miss["down_t_ms"]) + shift, 3)
        miss["up_t_ms"] = round(float(miss["up_t_ms"]) + shift, 3)


def _apply_batch_miss_cap(trials: list[dict[str, Any]], profile: dict[str, Any], rng: random.Random) -> None:
    try:
        observed_rate = max(0.0, float(profile.get("miss_rate", 0.0) or 0.0))
    except (TypeError, ValueError, AttributeError):
        observed_rate = 0.0
    allowed_rate = min(observed_rate, MAX_GLOBAL_MISS_RATE)
    allowed_count = int(round(len(trials) * allowed_rate))
    miss_indexes = [i for i, trial in enumerate(trials) if trial.get("miss_clicks")]
    rng.shuffle(miss_indexes)
    for index in miss_indexes[allowed_count:]:
        trials[index]["miss_clicks"] = []


def _compact_miss_recovery(trial: dict[str, Any], rng: random.Random) -> None:
    misses = trial.get("miss_clicks", [])
    if not isinstance(misses, list) or not misses:
        return

    miss = misses[0]
    points = trial["points"]
    click = trial["click"]
    miss_up = float(miss["up_t_ms"])
    before = [point for point in points if float(point["t_ms"]) <= miss_up] or [points[0]]
    sx, sy = float(miss["x"]), float(miss["y"])
    ex, ey = float(click["x"]), float(click["y"])
    duration = rng.uniform(65.0, 110.0)
    dx, dy = ex - sx, ey - sy
    length = max(1.0, math.hypot(dx, dy))
    px, py = -dy / length, dx / length
    curve = rng.gauss(0.0, min(2.0, length * 0.06))

    for index in range(1, 9):
        u = index / 8
        ease = u * u * (3.0 - 2.0 * u)
        side = math.sin(math.pi * u) * curve
        before.append({
            "t_ms": round(miss_up + duration * u, 3),
            "x": round(sx + dx * ease + px * side, 3),
            "y": round(sy + dy * ease + py * side, 3),
        })

    hold = max(25.0, float(click["up_t_ms"]) - float(click["down_t_ms"]))
    click_down = min(miss_up + MAX_MISS_RECOVERY_MS, miss_up + duration + rng.uniform(18.0, 48.0))
    click["down_t_ms"] = round(click_down, 3)
    click["up_t_ms"] = round(click_down + hold, 3)
    trial["points"] = before


def _rebuild_settle_phase(trial: dict[str, Any], entry_index: int, desired_delay: float, rng: random.Random) -> None:
    points = trial["points"]
    click = trial["click"]
    entry = points[entry_index]
    sx, sy = float(entry["x"]), float(entry["y"])
    ex, ey = float(click["x"]), float(click["y"])
    start_t = float(entry["t_ms"])
    duration = max(32.0, desired_delay)
    dx, dy = ex - sx, ey - sy
    length = max(1.0, math.hypot(dx, dy))
    px, py = -dy / length, dx / length
    curve = rng.gauss(0.0, min(1.8, length * 0.08))
    rebuilt = points[: entry_index + 1]
    steps = max(6, min(14, int(duration / 14.0)))

    for index in range(1, steps + 1):
        u = index / steps
        ease = u * u * (3.0 - 2.0 * u)
        side = math.sin(math.pi * u) * curve * (1.0 - u)
        rebuilt.append({
            "t_ms": round(start_t + duration * u, 3),
            "x": round(sx + dx * ease + px * side, 3),
            "y": round(sy + dy * ease + py * side, 3),
        })

    hold = max(25.0, float(click["up_t_ms"]) - float(click["down_t_ms"]))
    new_down = start_t + duration
    click["down_t_ms"] = round(new_down, 3)
    click["up_t_ms"] = round(new_down + hold, 3)
    trial["points"] = rebuilt


def _trim_click_delay(trial: dict[str, Any], rng: random.Random) -> None:
    points = trial["points"]
    click = trial["click"]
    if trial.get("miss_clicks"):
        last_time = float(points[-1]["t_ms"])
        hold = max(25.0, float(click["up_t_ms"]) - float(click["down_t_ms"]))
        click_down = max(float(click["down_t_ms"]), last_time + rng.uniform(18.0, 48.0))
        click["down_t_ms"] = round(click_down, 3)
        click["up_t_ms"] = round(click_down + hold, 3)
        return

    entry_index = _first_entry_index(points, trial["target"])
    if entry_index is None:
        return
    entry = float(points[entry_index]["t_ms"])
    current = float(click["down_t_ms"]) - entry
    if current > 360.0:
        desired = rng.uniform(145.0, 300.0)
    elif current < 32.0:
        desired = rng.uniform(38.0, 82.0)
    else:
        desired = current
    _rebuild_settle_phase(trial, entry_index, desired, rng)


def _retime_without_jumps(trial: dict[str, Any], cap_px_s: float = RAW_SPEED_CAP_PX_S) -> None:
    points = trial["points"]
    if len(points) < 2:
        return

    hold = max(25.0, float(trial["click"]["up_t_ms"]) - float(trial["click"]["down_t_ms"]))
    retimed = [dict(points[0])]
    for original_first, original_second in zip(points, points[1:]):
        previous_new = retimed[-1]
        distance = math.hypot(
            float(original_second["x"]) - float(original_first["x"]),
            float(original_second["y"]) - float(original_first["y"]),
        )
        original_dt = max(0.5, float(original_second["t_ms"]) - float(original_first["t_ms"]))
        physical_dt = distance / cap_px_s * 1000.0
        retimed.append({
            "t_ms": round(float(previous_new["t_ms"]) + max(original_dt, physical_dt), 3),
            "x": float(original_second["x"]),
            "y": float(original_second["y"]),
        })

    trial["points"] = retimed
    route_end = float(retimed[-1]["t_ms"])
    click_down = max(route_end, float(trial["click"]["down_t_ms"]))
    trial["click"]["down_t_ms"] = round(click_down, 3)
    trial["click"]["up_t_ms"] = round(click_down + hold, 3)


def _stretch_active_timeline(trial: dict[str, Any], factor: float) -> None:
    index = _first_motion_index(trial)
    if index is None or factor <= 1.0:
        return
    anchor = float(trial["points"][index - 1]["t_ms"]) if index > 0 else 0.0
    for point in trial["points"][index:]:
        point["t_ms"] = round(anchor + (float(point["t_ms"]) - anchor) * factor, 3)
    for key in ("down_t_ms", "up_t_ms"):
        trial["click"][key] = round(anchor + (float(trial["click"][key]) - anchor) * factor, 3)
    for miss in trial.get("miss_clicks", []):
        for key in ("down_t_ms", "up_t_ms"):
            miss[key] = round(anchor + (float(miss[key]) - anchor) * factor, 3)


def _rederive(trial: dict[str, Any]) -> None:
    trial["derived"] = derive_trial(trial["target"], trial["start"], trial["points"], trial["click"])


def _enforce_measured_speed_cap(trial: dict[str, Any], cap_px_s: float = MEASURED_SPEED_CAP_PX_S) -> None:
    # Metrics smooth the route before calculating velocity. A raw segment limiter alone
    # therefore cannot guarantee the published peak-speed metric. Stretch the active
    # timeline iteratively until the exact same derive_trial calculation is under cap.
    for _ in range(3):
        _rederive(trial)
        peak = float(trial["derived"].get("peak_speed_px_s", 0.0) or 0.0)
        if peak <= cap_px_s:
            return
        _stretch_active_timeline(trial, peak / cap_px_s * 1.01)
    _rederive(trial)


def simulate(plan: dict[str, Any], profile: dict[str, Any], seed: int | None = None) -> list[dict[str, Any]]:
    trials = base_simulate(plan, profile, seed)
    rng = random.Random((seed or int(plan.get("seed", 1))) ^ 0x5A17C0DE)
    _apply_batch_miss_cap(trials, profile, rng)

    for trial in trials:
        local = random.Random(rng.randrange(1, 2**31 - 1))
        trial["points"] = _continuous_route_cloud(
            trial["points"], trial["start"], trial["click"], trial["target"], local
        )
        _compact_miss_recovery(trial, local)
        _trim_click_delay(trial, local)
        _enforce_reaction_floor(trial)
        _retime_without_jumps(trial)
        _enforce_measured_speed_cap(trial)

    return trials
